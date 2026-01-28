#!/usr/bin/env python3
"""
Trial intervention runner built on the AG2 checkpoint system.

Workflow:
1. Read intervention_recommendation.json from the specified scenario directory.
2. Map each intervention to the corresponding message_appended checkpoint and insert the manager message.
3. Generate a patched checkpoint for each intervention and immediately resume via CheckpointRestorer.
4. Output every continuation result together with the patched checkpoint path for follow-up analysis.
"""

import argparse
import copy
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]

try:
    from checkpoint_system.restoration import CheckpointLoader, AgentRecreator
    from checkpoint_system.core import create_checkpoint_manager
    from checkpoint_system.wrappers import CheckpointingGroupChatManager
    from autogen.agentchat.groupchat import GroupChat
    from autogen import LLMConfig
    from utils import (
        AZURE_OPENAI_API_KEY_ENV_VAR,
        AZURE_OPENAI_API_VERSION_ENV_VAR,
        AZURE_OPENAI_ENDPOINT_ENV_VAR,
        DEFAULT_AZURE_OPENAI_API_VERSION,
    )
except ModuleNotFoundError:
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from checkpoint_system.restoration import CheckpointLoader, AgentRecreator
    from checkpoint_system.core import create_checkpoint_manager
    from checkpoint_system.wrappers import CheckpointingGroupChatManager
    from autogen.agentchat.groupchat import GroupChat
    from autogen import LLMConfig
    from utils import (
        AZURE_OPENAI_API_KEY_ENV_VAR,
        AZURE_OPENAI_API_VERSION_ENV_VAR,
        AZURE_OPENAI_ENDPOINT_ENV_VAR,
        DEFAULT_AZURE_OPENAI_API_VERSION,
    )


def _load_interventions(scenario_dir: Path) -> List[Dict[str, Any]]:
    file_path = scenario_dir / "intervention_recommendation.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Intervention file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Intervention file is empty, unable to continue")
    return data


def _resolve_checkpoint(checkpoints_dir: Path, step_idx: int) -> Path:
    pattern = f"checkpoint_{step_idx}_message_appended_*.json"
    matches = sorted(checkpoints_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No message_appended checkpoint found for step={step_idx}")
    return matches[-1]


def _extract_text(entry: Dict[str, Any]) -> str:
    if entry.get("replacement_text"):
        return entry.get("replacement_text") or ""
    suggestions = entry.get("suggestions") or {}
    if entry.get("category") == "plan_adjustment":
        return suggestions.get("plan_patch") or ""
    if entry.get("category") == "manager_instruction":
        return suggestions.get("chat_manager_instruction") or ""
    if entry.get("category") == "agent_instruction":
        return suggestions.get("agent_follow_up") or ""
    return suggestions.get("notes") or suggestions.get("replacement_text") or entry.get("raw", "")


def _load_chat_history(scenario_dir: Path) -> List[Dict[str, Any]]:
    enriched = scenario_dir / "chat_history_with_index.json"
    if enriched.exists():
        return json.loads(enriched.read_text(encoding="utf-8"))
    chat_history_path = scenario_dir / "chat_history.json"
    if chat_history_path.exists():
        data = json.loads(chat_history_path.read_text(encoding="utf-8"))
        return data.get("chat_history", [])
    raise FileNotFoundError("chat_history_with_index.json or chat_history.json not found")


def _build_step_lookup(chat_history: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    lookup: Dict[int, Dict[str, Any]] = {}
    for entry in chat_history:
        idx = entry.get("step_idx")
        if isinstance(idx, int):
            lookup[idx] = entry
    return lookup


def _map_steps_to_messages(
    chat_history: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> Dict[int, Optional[int]]:
    mapping: Dict[int, Optional[int]] = {}
    msg_idx = 0
    total_msgs = len(messages)
    for entry in chat_history:
        step_idx = entry.get("step_idx")
        if not isinstance(step_idx, int):
            continue
        if msg_idx < total_msgs:
            msg = messages[msg_idx]
            if (
                entry.get("name") == msg.get("name")
                and entry.get("content") == msg.get("content")
            ):
                mapping[step_idx] = msg_idx
                msg_idx += 1
                continue
        mapping[step_idx] = None
    return mapping


def _write_chat_history_with_index(chat_history: List[Dict[str, Any]], dest_path: Path) -> None:
    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(chat_history):
        entry["step_idx"] = idx
        item = dict(entry)
        normalized.append(item)
    dest_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_checkpoint_data(
    checkpoint_data: Dict[str, Any],
    entry: Dict[str, Any],
    step_idx: int,
    original_step: Dict[str, Any],
    message_index: Optional[int],
    intervention_text: str,
) -> None:
    groupchat_state = checkpoint_data.setdefault("groupchat_state", {})
    messages = groupchat_state.setdefault("messages", [])

    original_content = original_step.get("content", "")
    speaker_name = original_step.get("name")

    updated = False
    if message_index is not None:
        if not (0 <= message_index < len(messages)):
            raise IndexError(
                f"message_index {message_index} exceeds the number of messages (total {len(messages)})"
            )
        target_message = messages[message_index]
        original_content = target_message.get("content", original_content)
        speaker_name = target_message.get("name", speaker_name)
        target_message["content"] = intervention_text
        updated = True

        session_meta = checkpoint_data.setdefault("session_metadata", {})
        session_meta["action"] = "message_edited"
        session_meta["current_speaker"] = target_message.get("name")
        session_meta["message_content"] = intervention_text
        session_meta["round_number"] = checkpoint_data.get("current_round")

    checkpoint_data["timestamp"] = datetime.now().isoformat()
    checkpoint_data["checkpoint_id"] = f"{checkpoint_data.get('checkpoint_id', 'checkpoint')}_patched"

    # Synchronize every agent's history (including the chat_manager initial instructions)
    agent_states = checkpoint_data.get("agent_states", {})
    for agent_state in agent_states.values():
        convo = agent_state.get("_oai_messages") or {}
        for partner, history in convo.items():
            if not isinstance(history, list):
                continue
            for msg in history:
                if (
                    isinstance(msg, dict)
                    and msg.get("name") == speaker_name
                    and msg.get("content") == original_content
                ):
                    msg["content"] = intervention_text
                    msg["__intervened__"] = True
                    updated = True

    if not updated:
        raise ValueError("No dialog content found to edit; cannot apply the intervention")

    meta = checkpoint_data.setdefault("intervention_metadata", {})
    meta["applied_entry"] = entry
    meta["applied_at"] = datetime.now().isoformat()
    meta["step_idx"] = step_idx
    meta["message_index"] = message_index
    meta["speaker_name"] = speaker_name
    meta["original_content_length"] = len(original_content or "")


    meta["edited_step"] = step_idx


def _save_patched_checkpoint(trial_dir: Path, step_idx: int, patched_data: Dict[str, Any]) -> Path:
    trial_dir.mkdir(parents=True, exist_ok=True)
    patched_path = trial_dir / f"patched_checkpoint_step{step_idx}.json"
    patched_path.write_text(json.dumps(patched_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return patched_path


def _continue_from_data(
    trial_dir: Path,
    original_checkpoint: Path,
    patched_path: Path,
    checkpoint_data: Dict[str, Any],
    max_rounds: int,
    base_message_count: int,
) -> Dict[str, Any]:
    agents = AgentRecreator.recreate_agents_from_checkpoint(checkpoint_data)

    groupchat_state = checkpoint_data["groupchat_state"]
    groupchat = GroupChat(
        agents=agents,
        messages=groupchat_state["messages"],
        max_round=groupchat_state.get("max_round", max_rounds + checkpoint_data.get("current_round", 0))
    )

    manager_state = checkpoint_data["manager_state"]
    manager_llm_conf = manager_state.get("llm_config")
    if not manager_llm_conf:
        raise ValueError("manager_state.llm_config is missing; cannot resume")

    llm_config_data = dict(manager_llm_conf)
    llm_config_data.pop("azure_ad_token_provider", None)

    azure_endpoint = os.getenv(AZURE_OPENAI_ENDPOINT_ENV_VAR)
    azure_api_key = os.getenv(AZURE_OPENAI_API_KEY_ENV_VAR)
    azure_api_version = os.getenv(AZURE_OPENAI_API_VERSION_ENV_VAR, DEFAULT_AZURE_OPENAI_API_VERSION)

    if not azure_endpoint:
        raise RuntimeError(f"{AZURE_OPENAI_ENDPOINT_ENV_VAR} must be set to resume interventions.")
    if not azure_api_key:
        raise RuntimeError(f"{AZURE_OPENAI_API_KEY_ENV_VAR} must be set to resume interventions.")

    llm_config_data["api_type"] = "azure"
    llm_config_data["base_url"] = azure_endpoint
    llm_config_data["api_key"] = llm_config_data.get("api_key") or azure_api_key
    llm_config_data["api_version"] = llm_config_data.get("api_version") or azure_api_version
    if not llm_config_data.get("azure_deployment") and llm_config_data.get("model"):
        llm_config_data["azure_deployment"] = llm_config_data["model"]

    llm_config = LLMConfig(**llm_config_data)

    continuation_dir = trial_dir / "continuation"
    continuation_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_manager = create_checkpoint_manager(continuation_dir)

    manager_params = {
        "checkpoint_manager": checkpoint_manager,
        "groupchat": groupchat,
        "name": manager_state["name"],
        "system_message": manager_state["system_message"],
        "llm_config": llm_config,
        "human_input_mode": manager_state["human_input_mode"],
        "max_consecutive_auto_reply": manager_state["_max_consecutive_auto_reply"],
        "description": manager_state.get("description"),
    }

    termination_pattern = manager_state.get("termination_pattern")
    if termination_pattern == "SOLUTION_FOUND":
        manager_params["is_termination_msg"] = lambda message: "SOLUTION_FOUND" in (
            message.get("content", "") if isinstance(message, dict) else ""
        )

    chat_manager = CheckpointingGroupChatManager(**manager_params)

    AgentRecreator.restore_agent_message_histories(agents, chat_manager)

    # Reset auto-reply counters so interventions don't immediately trigger limits
    for agent in agents:
        reset_counter = getattr(agent, "reset_consecutive_auto_reply_counter", None)
        if callable(reset_counter):
            reset_counter()
    if hasattr(chat_manager, "reset_consecutive_auto_reply_counter"):
        chat_manager.reset_consecutive_auto_reply_counter()

    success, reason = chat_manager.continue_from_loaded_state(max_additional_rounds=max_rounds)

    all_messages = [copy.deepcopy(msg) for msg in groupchat.messages]
    new_messages = all_messages[base_message_count:]

    metadata_path = continuation_dir / "continuation_summary.json"
    metadata = {
        "patched_checkpoint": str(patched_path),
        "success": success,
        "termination_reason": reason,
        "continuation_dir": str(continuation_dir),
        "timestamp": datetime.now().isoformat(),
        "original_checkpoint": str(original_checkpoint),
        "new_messages_count": len(new_messages),
        "base_message_count": base_message_count,
        "total_messages": len(all_messages),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata["_all_messages"] = all_messages
    metadata["_new_messages"] = new_messages
    return metadata


def _coerce_int(value: Any) -> Any:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit() or ch == "-")
        if digits and digits not in {"-", ""}:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AG2 trial intervention runner")
    parser.add_argument("--exp_results_dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--max_rounds", type=int, default=50)
    args = parser.parse_args()

    scenario_dir = Path(args.exp_results_dir).expanduser().resolve() / args.scenario
    if not scenario_dir.exists():
        raise FileNotFoundError(f"Scenario directory does not exist: {scenario_dir}")

    interventions = _load_interventions(scenario_dir)
    base_chat_history = _load_chat_history(scenario_dir)
    trial_states: Dict[str, Dict[str, Any]] = {}
    checkpoints_dir = scenario_dir / "checkpoints"

    results: List[Dict[str, Any]] = []
    loader = CheckpointLoader()

    for entry in interventions:
        step_idx = int(entry.get("step", 0))
        checkpoint_path = _resolve_checkpoint(checkpoints_dir, step_idx)

        checkpoint_data = loader.load_checkpoint(checkpoint_path)
        text = _extract_text(entry).strip()
        if not text:
            raise ValueError(f"Intervention text is empty; cannot apply entry: {entry}")

        trial_index = _coerce_int(entry.get("trial_index"))
        if trial_index is not None:
            trial_dir = scenario_dir / f"trial_{trial_index}"
            trial_key = f"trial_{trial_index}"
        else:
            trial_dir = scenario_dir / f"trial_step_{step_idx}"
            trial_key = f"trial_step_{step_idx}"

        trial_state = trial_states.get(trial_key)
        if trial_state is None:
            trial_history = copy.deepcopy(base_chat_history)
            trial_states[trial_key] = {
                "history": trial_history,
                "step_lookup": _build_step_lookup(trial_history),
            }
            trial_state = trial_states[trial_key]

        chat_history = trial_state["history"]
        step_lookup = trial_state["step_lookup"]

        messages = checkpoint_data.get("groupchat_state", {}).get("messages", [])
        step_to_message = _map_steps_to_messages(chat_history, messages)
        message_index = step_to_message.get(step_idx)

        original_step = step_lookup.get(step_idx)
        if original_step is None:
            raise ValueError(f"chat_history does not contain a record for step_idx={step_idx}")

        patched = json.loads(json.dumps(checkpoint_data))
        original_step_snapshot = dict(original_step)

        _patch_checkpoint_data(
            patched,
            entry,
            step_idx,
            original_step_snapshot,
            message_index,
            text,
        )
        # Update the original message content in the local chat_history
        if original_step is not None:
            original_step["content"] = text

        patched_path = _save_patched_checkpoint(trial_dir, step_idx, patched)
        # Remove original records after the current step before appending new messages
        truncate_start = step_idx + 1
        if truncate_start < len(chat_history):
            del chat_history[truncate_start:]
            trial_state["step_lookup"] = _build_step_lookup(chat_history)
            step_lookup = trial_state["step_lookup"]

        summary = _continue_from_data(
            trial_dir,
            checkpoint_path,
            patched_path,
            patched,
            args.max_rounds,
            base_message_count=len(messages),
        )

        summary.pop("_all_messages", None)
        new_messages = summary.pop("_new_messages", [])

        # Append new messages to chat history
        next_idx = len(chat_history)
        for msg in new_messages:
            content = msg.get("content", "")
            if content is None:
                continue
            entry_obj = {
                "content": content,
                "role": msg.get("role"),
                "name": msg.get("name"),
                "step_idx": next_idx,
            }
            chat_history.append(entry_obj)
            next_idx += 1

        trial_state["step_lookup"] = _build_step_lookup(chat_history)

        continuation_dir_path = Path(summary["continuation_dir"])
        continuation_dir_path.mkdir(parents=True, exist_ok=True)
        _write_chat_history_with_index(
            chat_history,
            continuation_dir_path / "chat_history_with_index.json",
        )

        chat_history_path = continuation_dir_path / "chat_history_with_index.json"

        summary.update(
            {
                "scenario": entry.get("scenario"),
                "trial_index": entry.get("trial_index"),
                "step": step_idx,
                "trial_dir": str(trial_dir),
                "message_index": message_index,
                "chat_history_path": str(chat_history_path),
            }
        )
        results.append(summary)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
