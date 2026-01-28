#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
from openai import AzureOpenAI
import os

AZURE_OPENAI_ENDPOINT_ENV_VAR = "AZURE_OPENAI_ENDPOINT"
DEFAULT_AZURE_OPENAI_ENDPOINT = os.environ.get(AZURE_OPENAI_ENDPOINT_ENV_VAR)


PROJECT_ROOT = Path(__file__).parent.parent

SCENARIO_TMPL = PROJECT_ROOT / "Agents_Failure_Attribution/Who&When/Hand-Crafted/{sid}.json"

# Inline from failure_proposer.py
from typing import Tuple

def build_history_path(sid: str, round_id: str) -> Path:
    return PROJECT_ROOT / "logs" / f"scenario_{sid}" / str(round_id) / f"scenario_{sid}_history.json"

def load_problem_gt(sid: str) -> Tuple[str, str]:
    path = Path(str(SCENARIO_TMPL).format(sid=sid))
    obj = json.loads(path.read_text(encoding="utf-8"))
    q = obj.get("question") or obj.get("task") or obj.get("query") or ""
    gt = obj.get("ground_truth", "")
    return q, gt

def extract_steps_from_history(sid: str, history_path: Path) -> List[Dict[str, Any]]:
    """Extract GroupChatAgentResponse steps with timestamp and clean agent name"""
    path = history_path
    obj = json.loads(path.read_text(encoding="utf-8"))
    steps: List[Dict[str, Any]] = []

    def coerce_content(c):
        if isinstance(c, list):
            parts = [x for x in c if isinstance(x, str)]
            return "\n".join(parts)
        return str(c) if c is not None else ""

    def extract_clean_agent_name(name: str) -> str:
        if "_" in name:
            return name.split("_")[0]
        return name

    def try_collect_from_messages(messages: List[Dict[str, Any]]):
        for m in messages:
            inner = m.get("message", {})
            msg_type = inner.get("type")
            if msg_type == "GroupChatAgentResponse":
                raw_name = inner.get("name") or (
                    inner.get("response", {}).get("chat_message", {}).get("source")
                ) or "Unknown"
                clean_name = extract_clean_agent_name(str(raw_name))
                chat = inner.get("response", {}).get("chat_message", {})
                content = chat.get("content")
                timestamp = m.get("timestamp", 0)
                steps.append({
                    "name": clean_name,
                    "content": coerce_content(content),
                    "timestamp": timestamp
                })

    if "message_history" in obj:
        cur = str(obj.get("current_session", 0))
        session = obj.get("message_history", {}).get(cur, {})
        msgs = session.get("messages", [])
        try_collect_from_messages(msgs)
    elif isinstance(obj, list):
        try_collect_from_messages(obj)
    else:
        msgs = obj.get("messages", [])
        try_collect_from_messages(msgs)

    steps.sort(key=lambda x: x["timestamp"])
    for idx, step in enumerate(steps):
        step["step_idx"] = idx
    return steps

# Inline from intervention_recommender.parse_llm_json_relaxed
from typing import Optional as _Optional

def parse_llm_json_relaxed(text: str) -> _Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    if "```" in s:
        try:
            first = s.find("```")
            if first != -1:
                next_newline = s.find("\n", first + 3)
                if next_newline == -1:
                    next_newline = first + 3
                last = s.rfind("```")
                if last != -1 and last > next_newline:
                    inner = s[next_newline + 1:last].strip()
                    try:
                        return json.loads(inner)
                    except Exception:
                        pass
        except Exception:
            pass
    try:
        l = s.find("{")
        r = s.rfind("}")
        if l != -1 and r != -1 and r > l:
            inner = s[l:r+1]
            return json.loads(inner)
    except Exception:
        pass
    return None

    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)
    return (resp.choices[0].message.content or "").strip()


# Re-add client helpers correctly

def _make_client(azure_endpoint: str, api_version: str) -> AzureOpenAI:
    if not azure_endpoint:
        raise ValueError("Azure OpenAI endpoint is required to create a client.")
    return AzureOpenAI(azure_endpoint=azure_endpoint, api_version=api_version)


def _chat_once(client: AzureOpenAI, model: str, messages: List[Dict[str, str]], max_tokens: int = 1024) -> str:
    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)
    return (resp.choices[0].message.content or "").strip()

def _trial_context_window(steps: List[Dict[str, Any]], fail_idx: int, window: int = 2) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if fail_idx is None:
        return out
    start = max(0, fail_idx - window)
    end = fail_idx
    for i in range(start, end + 1):
        s = steps[i]
        out.append({"idx": i, "name": s.get("name", ""), "content": s.get("content", ""), "is_failed": i == fail_idx})
    return out

def _build_intervention_prompt(problem: str, ground_truth: str, step_idx: int, agent: str, reason: Optional[str], context_window: List[Dict[str, Any]], trial_index: Optional[int] = None, trial_plan: Optional[List[Any]] = None, trial_progress: Optional[Dict[str, Any]] = None, trial_context: Optional[str] = None, trial_reflection: Optional[str] = None, prior_trials_summary: str = "", trial_execution: Optional[str] = None, trial_overall_summary: Optional[str] = None) -> str:
    gt_text = f"{ground_truth}\n\n" if ground_truth else ""
    ctx_lines = []
    for s in context_window:
        ctx_lines.append(f"[Step {s['idx']}] {s['name']}: {s['content']}")
    ctx = "\n".join(ctx_lines)
    plan_text = ""
    if isinstance(trial_plan, list) and trial_plan:
        plan_text = "\n".join(str(x) for x in trial_plan)
    prog_text = ""
    if isinstance(trial_progress, dict) and trial_progress:
        ff = trial_progress.get("fully_fulfilled_plan_steps") or []
        pf = trial_progress.get("partially_fulfilled_plan_steps") or []
        uf = trial_progress.get("unfulfilled_plan_steps") or []
        prog_text = (
            f"Fully fulfilled: {ff}\n"
            f"Partially fulfilled: {pf}\n"
            f"Unfulfilled: {uf}"
        )
    trial_hdr = f"Trial index: {trial_index}\n" if trial_index is not None else ""
    trial_ctx = trial_context or ""
    trial_refl = trial_reflection or ""
    prior_text = prior_trials_summary or ""
    trial_exec = trial_execution or ""
    trial_overall = trial_overall_summary or ""
    return (
        "You are an expert in debugging multi-agent systems. A failure analyzer has examined a Magentic-One execution and located a problematic step. "
        "Use this as guidance to design a precise, minimal intervention that eliminates the root cause.\n\n"
        "## Task Background\n"
        f"Original task: {problem}\n"
        f"Reference ground truth (for your guidance only): {gt_text}"
        "The overall path has been split into multiple trials. Below are summaries of previous trials:\n"
        f"{prior_text}\n\n"
        "Here are the details of the current trial:\n"
        f"{trial_hdr}"
        f"Context: {trial_ctx}\n"
        f"Plan:\n{plan_text}\n"
        f"Execution: {trial_exec}\n"
        f"Progress:\n{prog_text}\n"
        f"Reflection: {trial_refl}\n"
        f"Overall summary: {trial_overall}\n\n"
        "Specific failure:\n"
        f"Failed step index: {step_idx}\n"
        f"Failed agent: {agent}\n"
        f"Diagnosed reason: {reason}\n\n"
        "## Execution Context\n"
        "Below are the two steps immediately before the failure and the failed step itself:\n"
        f"{ctx}\n\n"
        "## System specifics and intervention policy:\n"
        "- If failure is in Orchestrator: Task Full Ledger issues -> provide ONLY the minimal replacement snippet(s) for the affected section(s): Facts and/or Plan. Use tags [FACTS_REPLACEMENT]: ... and/or [PLAN_REPLACEMENT]: ...; do not output the entire Task Full Ledger. Use this only when the failed content is the Task Full Ledger content (starts with 'We are working to address the following user request:' and includes the Facts/Plan sections).\n"
        "- If Orchestrator instruction is wrong/ambiguous -> provide the exact corrected instruction as a single atomic next step. If the message is not the Task Full Ledger scaffold, or when unsure, treat it as orchestrator_instruction.\n"
        "- If a subagent failed -> infer, from the provided context, how that subagent or tool should have acted; rewrite the Orchestrator's instruction to that subagent/tool so that it leads to the correct behavior.\n"
        "- Keep changes minimal and targeted. Avoid global resets.\n"
        "- Do not include any ground truth in the intervention message.\n\n"
        "Return STRICT JSON with the following schema:\n"
        "{\n"
        "  \"category\": one of [\"orchestrator_ledger\", \"orchestrator_instruction\", \"subagent_instruction\"],\n"
        "  \"replacement_text\": \"exact text that should replace the problematic content\"\n"
        "}\n"
        "Respond with JSON only, no extra commentary."
    )

def _coerce_int(x):
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        d = "".join(ch for ch in x if ch.isdigit())
        return int(d) if d else None
    return None

def _build_prior_trials_summary(trials: List[Dict[str, Any]], current_trial_index: int, max_trials: int = 3) -> str:
    prev: List[Dict[str, Any]] = []
    for t in trials:
        ti = _coerce_int(t.get("trial_index"))
        if ti is None:
            continue
        if ti < current_trial_index:
            prev.append(t)
    if not prev:
        return ""
    prev = prev[-max_trials:]
    lines: List[str] = []
    for t in prev:
        ti = _coerce_int(t.get("trial_index"))
        overall = t.get("trial_overall_summary") or ""
        lines.append(f"Trial {ti}: {overall}")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Trial-based Intervention Recommender")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--round", default="1")
    ap.add_argument(
        "--azure-endpoint",
        default=DEFAULT_AZURE_OPENAI_ENDPOINT,
        help="Azure OpenAI endpoint (default from AZURE_OPENAI_ENDPOINT env var)",
    )
    ap.add_argument("--api-version", default="2024-08-01-preview")
    ap.add_argument("--model", default="gpt-4o", help="Model to use (default: gpt-4o)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--hist_path", default=None, help="Path to the history file. If not provided, will be constructed from scenario and round.")
    args = ap.parse_args()
    if not args.azure_endpoint:
        ap.error(
            f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
        )

    sid = str(args.scenario).strip()
    problem, gt = load_problem_gt(sid)

    hist_path = Path(args.hist_path) if args.hist_path is not None else build_history_path(sid, args.round)
    if not hist_path.exists():
        print(json.dumps({"scenario": sid, "error": f"history not found: {str(hist_path)}"}, ensure_ascii=False))
        return
    steps = extract_steps_from_history(sid, history_path=hist_path)
    if not steps:
        print(json.dumps({"scenario": sid, "error": "no steps extracted"}, ensure_ascii=False))
        return

    ts_map = {int(s["step_idx"]): s.get("timestamp") for s in steps}

    trial_path = hist_path.parent / f"trial_summary_scenario_{sid}_{args.model}.json"
    if not trial_path.exists():
        print(json.dumps({"scenario": sid, "error": f"trial summary not found: {str(trial_path)}"}, ensure_ascii=False))
        return

    trials = json.loads(trial_path.read_text(encoding="utf-8"))

    client = _make_client(args.azure_endpoint, args.api_version)

    outputs: List[Dict[str, Any]] = []

    for t in trials:
        t_idx = _coerce_int(t.get("trial_index"))
        if t_idx is None:
            continue
        is_succeed = bool(t.get("is_succeed", False))
        if is_succeed:
            continue
        m_idx = _coerce_int(t.get("mistake_step_index"))
        if m_idx is None:
            continue
        if not (0 <= m_idx < len(steps)):
            continue
        agent = t.get("mistake_agent") or steps[m_idx].get("name", "Unknown")
        reason = t.get("mistake_reason") or t.get("trial_overall_summary") or ""
        ts = t.get("mistake_step_timestamp")
        if ts is None:
            ts = ts_map.get(m_idx)
        ctx = _trial_context_window(steps, m_idx, window=2)
        prior_summary = _build_prior_trials_summary(trials, t_idx)
        prompt = _build_intervention_prompt(
            problem,
            gt,
            m_idx,
            agent,
            reason,
            ctx,
            trial_index=t_idx,
            trial_plan=t.get("trial_plan"),
            trial_progress=t.get("trial_progress"),
            trial_context=t.get("trial_context"),
            trial_reflection=t.get("trial_reflection"),
            prior_trials_summary=prior_summary,
            trial_execution=t.get("trial_execution"),
            trial_overall_summary=t.get("trial_overall_summary"),
        )
        messages = [
            {"role": "system", "content": "You write precise, minimal, and structured interventions for Magentic-One multi-agent runs."},
            {"role": "user", "content": prompt},
        ]
        ans = _chat_once(client, args.model, messages, args.max_tokens)
        parsed = parse_llm_json_relaxed(ans) or {}
        category = parsed.get("category", "other")
        replacement_text = parsed.get("replacement_text", "")
        def _map_suggestions(cat: str, rep: str) -> Dict[str, Any]:
            if cat == "orchestrator_instruction":
                return {"new_instruction": rep or "Please refine instruction as suggested."}
            if cat == "orchestrator_ledger":
                return {"ledger": {"add_facts": [], "remove_facts": [], "plan_edits": [x for x in [rep] if x]}}
            if cat == "subagent_instruction":
                return {"subagent_guidance": {"previous_instruction_fix": rep}}
            return {}
        out = {
            "scenario": sid,
            "round_id": str(args.round),
            "trial_index": t_idx,
            "step": m_idx,
            "agent": agent,
            "timestamp": ts,
            "category": category,
            "suggestions": _map_suggestions(category, replacement_text),
            "raw": ans,
        }
        outputs.append(out)

    out_path = hist_path.parent / f"intervention_trial_scenario_{sid}.json"
    out_path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))

if __name__ == "__main__":
    main()
