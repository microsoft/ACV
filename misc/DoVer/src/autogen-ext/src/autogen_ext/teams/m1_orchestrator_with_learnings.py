from __future__ import annotations

import os
from typing import List

from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.messages import TextMessage  # noqa: F401  # may be useful for future logging
from autogen_agentchat.teams._group_chat._events import GroupChatTermination
from autogen_agentchat.teams._group_chat._magentic_one._magentic_one_orchestrator import (
    MagenticOneOrchestrator,
)
from autogen_core.models import LLMMessage, SystemMessage


SYSTEM_LEARNINGS_TEMPLATE = """
These system learnings summarize patterns from prior traces so the next instruction applies proven tactics and avoids repeated failure modes.\n\nBefore each instruction (fixed template):\n1) ActiveContexts → which listed contexts match the current task/state.\n2) TacticsToApply → pick <Can do> tactics from those contexts; if none fit, specify a safeguard that neutralizes the relevant <Cannot do> risk.\n3) ExpectedChange → the concrete observation expected next (state/module/section delta, new artifact/log, safeguard confirmation).\n4) Validation & Stop → the evidence to collect and the stop/escalation condition.\n\nAction selection (agent-agnostic):\n- Prefer tactics that yield verifiable new evidence in the fewest steps; if a higher-leverage tactic is inapplicable, say why and choose the next best.\n- Budget: do not retry the same tactic > 3 times without escalation (change tactic/cue or switch agent).\n\nLoop assessment (multi-agent):\n- Progress if NEW evidence appears (state/module/section change; new snippet/log ≥ ~80 chars; new artifact; different tactic/safeguard; different agent engaged for a distinct capability).\n- Set is_in_loop = true only if across ≥ 3 consecutive turns the SAME context, SAME tactic (by any agent), and SAME resulting observation repeat with no new evidence and no escalation.\n\nEvidence signals (examples):\n- Changed state/module/section; new snippet/log; created/opened artifact (URL/file/handle); selector/cue used; safeguard executed; error reproduced/resolved.\n\nOutput discipline:\n- Produce ONLY the JSON object required by the user-provided schema (no extra text).\n\n
"""

SYSTEM_LEARNINGS_TEMPLATE_2 = """
You are an LLM-based multi-agent system that coordinates specialized agents to solve complex tasks. Convert prior learnings into proven tactics and avoid repeated failure modes.\n\nAgents available:\n- FileSurfer — handles local files.\n- WebSurfer — performs web searches; opens pages; interacts with content; can summarize pages; can wait for slow pages.\n- Coder — language/Python/Linux generalist for reasoning and coding.\n- ComputerTerminal — runs ONLY user-specified scripts (python or sh code blocks).\n- MagenticOneOrchestrator — plans and assigns work across agents.\n- System — the overall system orchestrating multiple agents to work together on complex tasks.\n\nLearnings input & schema:\n- You will receive agent- and context-specific learnings capturing strengths <Can do> and weaknesses <Cannot do>. If no agent fits, set target_agent_name = <System>.\n- The learnings are organized in the following markdown format:\nmarkdown\n<target_agent_name>\n - Context: <Description of the context or task type>.\n - Can do:\n - <Specific capability or strength demonstrated in this context>.\n - <Another capability or strength>.\n - Cannot do:\n - <Specific limitation or failure observed in this context>.\n - <Another limitation or failure>.\n<another_target_agent_name>\n - Context: <Description of another context or task type>.\n - Can do:\n - <Specific capability or strength demonstrated in this context>.\n - Cannot do:\n - <Specific limitation or failure observed in this context>.\n\n- You MUST parse and use these learnings to guide task assignment and instruction design.\n\nPolicy for using learnings:\n- When the current task overlaps a listed Context, treat matching <Can do> items as PROVEN tactics and bake them into the next instruction.\n- For each relevant <Cannot do> item: avoid assigning that shape of task to the limited agent OR add explicit guardrails plus validation/evidence checks.\n- Always choose the agent whose strengths best fit the required capability; if assigning into a weakness is unavoidable, include safeguards and verification.\n\nInstruction planning (fill BEFORE each instruction):\n1) ActiveContexts: which listed contexts match the current task/state.\n2) TacticsToApply: select applicable <Can do> tactics; if none fit, specify a safeguard to neutralize the most relevant <Cannot do> risk.\n3) ExpectedChange: the concrete observation expected next (state/module/section delta; new artifact/log; or safeguard confirmation).\n4) Validation & Stop: the exact evidence to collect and the stop/escalation condition.\n\nAction selection rules (agent-agnostic):\n- Prefer tactics that yield verifiable NEW evidence in the fewest steps.\n- If a higher-leverage tactic is inapplicable, state why and choose the next best option.\n- Budget: do NOT retry the same tactic > 3 times without escalation (change tactic/cue or switch agent or refine goal).\n\nEvidence signals (examples):\n- Changed state/module/section; new snippet/log; created/opened artifact (URL/file/handle); selector/cue used; safeguard executed; error reproduced/resolved.\n\nOutput discipline:\n- Produce ONLY the JSON object required by the user-provided schema (no extra text).\n\n
"""

class M1OrchestratorWithLearnings(MagenticOneOrchestrator):
    """Inject a fixed learnings block into the Task Ledger prompts.

    The block is emitted on the outer-loop prompt right after the team section
    and immediately before the fact sheet header. Re-injection behaviour is
    controlled via ``first_time_only``.
    """

    def __init__(
        self,
        name: str,
        group_topic_type: str,
        output_topic_type: str,
        participant_topic_types: List[str],
        participant_names: List[str],
        participant_descriptions: List[str],
        max_turns: int | None,
        message_factory,
        model_client,
        max_stalls: int,
        final_answer_prompt: str,
        output_message_queue: "asyncio.Queue[BaseAgentEvent | BaseChatMessage | GroupChatTermination]",
        termination_condition,
        emit_team_events: bool,
        *,
        learnings_enabled: bool = False,
        learnings_text: str | None = None,
        first_time_only: bool = True,
        add_system_prompt: bool = False,
    ) -> None:
        super().__init__(
            name,
            group_topic_type,
            output_topic_type,
            participant_topic_types,
            participant_names,
            participant_descriptions,
            max_turns,
            message_factory,
            model_client,
            max_stalls,
            final_answer_prompt,
            output_message_queue,
            termination_condition,
            emit_team_events,
        )
        self._learnings_enabled = bool(learnings_enabled)
        self._learnings_text = str(learnings_text) if learnings_text else None
        self._first_time_only = bool(first_time_only)
        self._add_system_prompt = bool(add_system_prompt)
        self._did_inject_once = False

        if self._learnings_enabled:
            additions = (
                "MagenticOneOrchestrator: An orchestrator agent that coordinates the actions of other agents to achieve high-level goals.",
                "System: The overall system orchestrating multiple agents to work together on complex tasks.",
            )
            joined = "\n".join(additions)
            self._team_description = f"{self._team_description}\n{joined}" if self._team_description else joined

    def _build_system_prompt(self) -> str | None:
        if not self._add_system_prompt:
            return None
        if not self._learnings_text:
            return None
        normalized = self._learnings_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return None
        template_choice = os.environ.get("M1_SYSTEM_PROMPT_TEMPLATE", "1")
        base_template = SYSTEM_LEARNINGS_TEMPLATE if template_choice != "2" else SYSTEM_LEARNINGS_TEMPLATE_2
        base_template = base_template.rstrip()
        if base_template:
            return f"{base_template}\n\n{normalized}"
        return normalized

    def _get_learnings_payload(self) -> str | None:
        if not self._learnings_enabled or not self._learnings_text:
            return None
        if self._first_time_only and self._did_inject_once:
            return None
        normalized = self._learnings_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        return normalized or None

    def _inject_learnings(self, base_text: str) -> str:
        learnings = self._get_learnings_payload()
        if not learnings:
            return base_text

        anchor_fact_sheet = "Here is an initial fact sheet to consider:"
        insert_block = (
            "Prior-run learnings (agent strengths vs gaps across different contexts):\n\n"
            f"{learnings}\n\n\n"
        )

        idx = base_text.find(anchor_fact_sheet)
        if idx == -1:
            # Fall back to appending if the anchor is missing.
            new_text = base_text.rstrip("\n") + "\n\n" + insert_block
        else:
            new_text = base_text[:idx] + insert_block + base_text[idx:]

        self._did_inject_once = True
        return new_text

    # Override prompt builder used by _reenter_outer_loop
    def _get_task_ledger_full_prompt(self, task: str, team: str, facts: str, plan: str) -> str:  # type: ignore[override]
        base = super()._get_task_ledger_full_prompt(task, team, facts, plan)
        return self._inject_learnings(base)

    def _get_progress_ledger_prompt(self, task: str, team: str, names: List[str]) -> str:  # type: ignore[override]
        base = super()._get_progress_ledger_prompt(task, team, names)
        if not (self._learnings_enabled and self._learnings_text):
            return base

        anchor = "To make progress on the request"
        reminder = (
            "\nBefore answering, revisit the prior-run learnings captured from earlier traces. "
            "If the next instruction touches a recorded <Context>, lean on that block's <Can do> moves and "
            "explicitly close the <Cannot do> gaps with concrete steps or guardrails. "
            "Use those insights to craft a sharper next instruction, including any validation or evidence checks "
            "needed to keep the team precise and avoid past misses.\n\n"
        )

        learnings = self._get_learnings_payload()
        if learnings:
            reminder = f"{reminder}{learnings}\n\n"
        idx = base.find(anchor)
        if idx != -1:
            return f"{base[:idx]}{reminder}{base[idx:]}"

        return f"{base}{reminder}"

    def _get_task_ledger_plan_prompt(self, team: str) -> str:  # type: ignore[override]
        base = super()._get_task_ledger_plan_prompt(team)
        learnings = self._get_learnings_payload()
        if not learnings:
            return base

        anchor = "Based on the team composition"
        insert_block = (
            "Consider these prior run learnings (agent strengths vs gaps across different contexts):\n"
            f"{learnings}\n\n\n"
        )
        idx = base.find(anchor)
        if idx != -1:
            self._did_inject_once = True
            return base[:idx] + insert_block + base[idx:]

        self._did_inject_once = True
        suffix = "\n" if not base.endswith("\n") else ""
        return base + suffix + insert_block

    def _get_task_ledger_plan_update_prompt(self, team: str) -> str:  # type: ignore[override]
        base = super()._get_task_ledger_plan_update_prompt(team)
        learnings = self._get_learnings_payload()
        if not learnings:
            return base

        insert_block = (
            "\nConsider these prior run learnings (agent strengths vs gaps across different contexts):\n"
            f"{learnings}\n\n\n"
        )
        self._did_inject_once = True
        return base + insert_block

    def _thread_to_context(self) -> List[LLMMessage]:  # type: ignore[override]
        context = super()._thread_to_context()
        if not self._add_system_prompt:
            return context
        system_prompt = self._build_system_prompt()
        if system_prompt and (not context or not isinstance(context[0], SystemMessage)):
            context.insert(0, SystemMessage(content=system_prompt))
        return context

