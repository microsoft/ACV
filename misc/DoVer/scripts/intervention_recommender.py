#!/usr/bin/env python3
"""
Intervention Recommender (OpenAI API, round-aware)

Purpose:
- Combine Failure Proposer output (locates erroneous step/agent/reason/timestamp) with the specified round's session history,
  call the LLM to generate actionable intervention suggestions (modify orchestrator ledger/instruction/sub-agent guidance, etc.).
- Relies on a standard OpenAI API key (set `OPENAI_API_KEY` or pass `--api-key`).

I/O conventions (per-round):
- Read failure file: logs/scenario_{sid}/{round}/failure_{method}_{prompt}.json
- Read history file: logs/scenario_{sid}/{round}/scenario_{sid}_history.json
- Save intervention: logs/scenario_{sid}/{round}/intervention_{method}_{prompt}.json

Outputs JSON to stdout with fields:
  {
    "scenario": "1",
    "round_id": "1",
    "step": 7,
    "agent": "WebSurfer",
    "timestamp": 20,
    "category": "subagent_instruction" | "orchestrator_ledger" | "orchestrator_instruction" | "other",
    "corrected_content": "...",
    "injection_message": "...",
    "raw": "... original LLM text ..."
  }
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from openai import OpenAI

# Auto-detect project root
PROJECT_ROOT = Path(__file__).parent.parent
SCENARIO_META_TMPL = PROJECT_ROOT / "Agents_Failure_Attribution/Who&When/Hand-Crafted/{sid}.json"

MODEL_NAME_MAP = {
    "gpt-4o": "gpt-4o-20241120",
    "gpt4": "gpt-4o-20241120",
    "gpt4o-mini": "gpt-4o-mini-20240718",
    "gpt-4o-20240513": "gpt-4o-20240513",
    "gpt-4o-20241120-2": "gpt-4o-20241120-2",
}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --------- IO helpers ---------

def load_meta(sid: str) -> Dict[str, Any]:
    p = Path(str(SCENARIO_META_TMPL).format(sid=sid))
    return json.loads(p.read_text(encoding="utf-8"))


def extract_steps_from_history(hist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of steps from GroupChatAgentResponse with name/content/timestamp."""
    steps: List[Dict[str, Any]] = []

    def coerce_content(c):
        if isinstance(c, list):
            # multimodal content: keep only text parts, join
            parts = [x for x in c if isinstance(x, str)]
            return "\n".join(parts)
        return str(c) if c is not None else ""

    def try_collect_from_messages(messages: List[Dict[str, Any]]):
        for m in messages:
            inner = m.get("message", {})
            msg_type = inner.get("type")
            if msg_type == "GroupChatAgentResponse":
                name = inner.get("name") or (
                    inner.get("response", {}).get("chat_message", {}).get("source")
                ) or "Unknown"
                chat = inner.get("response", {}).get("chat_message", {})
                content = chat.get("content")
                ts = m.get("timestamp")
                steps.append({"name": str(name), "content": coerce_content(content), "timestamp": ts})

    if "message_history" in hist:
        cur = str(hist.get("current_session", 0))
        session = hist.get("message_history", {}).get(cur, {})
        msgs = session.get("messages", [])
        try_collect_from_messages(msgs)
    elif isinstance(hist, list):
        try_collect_from_messages(hist)
    else:
        # fallback: scan common key
        msgs = hist.get("messages", [])
        try_collect_from_messages(msgs)

    # ensure stable order by timestamp if present
    try:
        steps.sort(key=lambda x: x.get("timestamp") or 0)
    except Exception:
        pass

    return steps


# --------- OpenAI client ---------

def make_openai_client(api_base: Optional[str], api_key: Optional[str]) -> OpenAI:
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY must be set (or pass --api-key) to call OpenAI models.")
    client_kwargs: Dict[str, Any] = {"api_key": resolved_api_key}
    base_url = api_base or os.getenv("OPENAI_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)


def chat_once(client: OpenAI, model: str, messages: List[Dict[str, str]], max_tokens: int = 1024) -> str:
    resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)
    return (resp.choices[0].message.content or "").strip()


# Robust JSON parser for LLM outputs wrapped in code fences or with extra text
from typing import Optional as _Optional

def parse_llm_json_relaxed(text: str) -> _Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    # Attempt 1: direct JSON
    try:
        return json.loads(s)
    except Exception:
        pass
    # Attempt 2: fenced code block ```json ... ``` or ``` ... ```
    if "```" in s:
        try:
            first = s.find("```")
            if first != -1:
                # skip language tag like ```json
                next_newline = s.find("\n", first + 3)
                if next_newline == -1:
                    next_newline = first + 3
                # find closing fence
                last = s.rfind("```")
                if last != -1 and last > next_newline:
                    inner = s[next_newline + 1:last].strip()
                    try:
                        return json.loads(inner)
                    except Exception:
                        pass
        except Exception:
            pass
    # Attempt 3: substring from first '{' to last '}'
    try:
        l = s.find("{")
        r = s.rfind("}")
        if l != -1 and r != -1 and r > l:
            inner = s[l:r+1]
            return json.loads(inner)
    except Exception:
        pass
    return None


# --------- Prompt Templates ---------

def build_intervention_prompt(problem: str, ground_truth: str, step_idx: int, agent: str, reason: Optional[str], context_window: List[Dict[str, Any]]) -> str:
    gt_text = f"{ground_truth}\n\n" if ground_truth else ""
    ctx_lines = []
    for s in context_window:
        ctx_lines.append(f"[Step {s['idx']}] {s['name']}: {s['content']}")
    ctx = "\n".join(ctx_lines)

    return (
        "You are an expert in debugging multi-agent systems. A failure proposer has analyzed a Magentic-One execution and identified a problematic step. "
        "Use this as guidance to design a precise, minimal intervention that fixes the root cause.\n\n"
        f"## Task Context\n"
        f"Here is the original task: {problem}\n"
        f"And here is the ground truth for guidance: {gt_text}"
        f"## Failure Analysis\n"
        f"Failed step index: {step_idx}\n"
        f"Failed agent: {agent}\n"
        f"Diagnosed reason: {reason}\n\n"
        f"## Execution Context\n"
        f"Here are the two steps immediately before the failure and the failed step itself:\n"
        f"{ctx}\n\n"
        "## System specifics and intervention policy:\n"
        "- If failure is in Orchestrator: Task Full Ledger issues -> provide ONLY the minimal replacement snippet(s) for the affected section(s): Facts and/or Plan. Use tags [FACTS_REPLACEMENT]: ... and/or [PLAN_REPLACEMENT]: ...; do not output the entire Task Full Ledger. Use this only when the failed content is the Task Full Ledger content (starts with 'We are working to address the following user request:' and includes the Facts/Plan sections).\n"
        "- If Orchestrator instruction is wrong/ambiguous -> provide the exact corrected instruction as a single atomic next step. If the message is not the Task Full Ledger scaffold, or when unsure, treat it as orchestrator_instruction.\n"
        "- If a subagent failed -> infer, from the provided context, how that subagent or tool should have acted; rewrite the Orchestrator's instruction to that subagent/tool so that it leads to the correct behavior.\n"
        "- Keep changes minimal and targeted. Avoid global resets.\n"
        "- Do not give any ground truth in the intervention message.\n\n"
        "Return STRICT JSON with the following schema:\n"
        "{\n"
        "  \"category\": one of [\"orchestrator_ledger\", \"orchestrator_instruction\", \"subagent_instruction\"],\n"
        "  \"replacement_text\": \"exact text that should replace the problematic content\"\n"
        "}\n"
        "Respond with JSON only, no extra commentary."
    )


# --------- Main logic ---------

def pick_context_window(steps: List[Dict[str, Any]], fail_idx: int, window: int = 2) -> List[Dict[str, Any]]:
    """Return the previous `window` steps PLUS the failed step itself.
    - Includes at most `window` steps before the failed step
    - Always includes the failed step at the end
    """
    out: List[Dict[str, Any]] = []
    if fail_idx is None:
        return out
    start = max(0, fail_idx - window)
    end = fail_idx
    for i in range(start, end + 1):
        s = steps[i]
        out.append({
            "idx": i,
            "name": s.get("name", ""),
            "content": s.get("content", ""),
            "is_failed": i == fail_idx,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Intervention Recommender (OpenAI API, round-aware)")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--round", default="1")
    ap.add_argument("--prompt-template", default="add_guidance")
    ap.add_argument("--failure-method", default="all_at_once", choices=["step_by_step", "all_at_once", "binary_search"])
    ap.add_argument("--api-base", default="https://api.openai.com/v1", help="Override the OpenAI API base URL.")
    ap.add_argument("--api-key", default=None, help="OpenAI API key (defaults to OPENAI_API_KEY).")
    ap.add_argument("--model", default="gpt-4o", choices=list(MODEL_NAME_MAP.keys()))
    ap.add_argument("--max-tokens", type=int, default=1024)
    args = ap.parse_args()

    sid = str(args.scenario)
    round_id = str(args.round)
    method = str(args.failure_method)
    prompt_tmpl = str(args.prompt_template)

    # 1) Read failure file directly (no proposer run here)
    failure_path = PROJECT_ROOT / "logs" / f"scenario_{sid}" / str(round_id) / f"failure_{method}_{prompt_tmpl}.json"
    if not failure_path.exists():
        print(json.dumps({"scenario": sid, "round_id": round_id, "found": False, "error": f"failure file not found: {failure_path}"}, ensure_ascii=False))
        return
    try:
        fail = json.loads(failure_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"scenario": sid, "round_id": round_id, "found": False, "error": f"failed to parse failure json: {e}"}, ensure_ascii=False))
        return

    agent = str(fail.get("agent", "Unknown"))
    reason = fail.get("reason") or fail.get("raw")
    failed_timestamp = fail.get("step_timestamp") or fail.get("timestamp")

    step_val = fail.get("step")
    step_idx = None
    try:
        step_idx = int(step_val) if step_val is not None else None
    except Exception:
        step_idx = None

    # 2) Load meta + per-round history and extract steps
    meta = load_meta(sid)
    problem = meta.get("question") or meta.get("task") or meta.get("query") or ""
    gt = meta.get("ground_truth", "")

    history_path = PROJECT_ROOT / "logs" / f"scenario_{sid}" / str(round_id) / f"scenario_{sid}_history.json"
    if not history_path.exists():
        print(json.dumps({"scenario": sid, "round_id": round_id, "found": False, "error": f"history file not found: {history_path}"}, ensure_ascii=False))
        return
    try:
        hist = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"scenario": sid, "round_id": round_id, "found": False, "error": f"failed to parse history json: {e}"}, ensure_ascii=False))
        return

    steps = extract_steps_from_history(hist)

    # Prefer locating failed step by timestamp; fallback to step index from failure json
    if step_idx is None and failed_timestamp is not None:
        for i, s in enumerate(steps):
            if s.get("timestamp") == failed_timestamp:
                step_idx = i
                break

    # Ensure we use the exact timestamp from history for the failed step
    if step_idx is not None and 0 <= step_idx < len(steps):
        failed_timestamp = steps[step_idx].get("timestamp")

    if step_idx is None or not (0 <= step_idx < len(steps)):
        print(json.dumps({"scenario": sid, "round_id": round_id, "found": False, "error": "failed step index not resolved"}, ensure_ascii=False))
        return

    # 3) Build context using ONLY previous two steps (exclude the failed step)
    ctx = pick_context_window(steps, step_idx, window=2)

    # 4) LLM prompt for interventions
    client = make_openai_client(args.api_base, args.api_key)
    model_actual = MODEL_NAME_MAP.get(args.model, args.model)

    prompt = build_intervention_prompt(problem, gt, step_idx, agent, reason, ctx)
    messages = [
        {"role": "system", "content": "You write precise, minimal, and structured interventions for Magentic-One multi-agent runs."},
        {"role": "user", "content": prompt},
    ]
    ans = chat_once(client, model_actual, messages, args.max_tokens)

    # 5) Parse JSON; map to structured suggestions expected by intervener
    def to_suggestions(category: str, corrected: str, injected: str) -> Dict[str, Any]:
        # We now expect a single replacement_text from the model. Map it accordingly.
        replacement = corrected or injected
        if category == "orchestrator_instruction":
            return {"new_instruction": replacement or "Please refine instruction as suggested."}
        if category == "orchestrator_ledger":
            return {"ledger": {"add_facts": [], "remove_facts": [], "plan_edits": [x for x in [replacement] if x]}}
        if category == "subagent_instruction":
            return {"subagent_guidance": {"previous_instruction_fix": replacement}}
        return {}

    out: Dict[str, Any]
    parsed = parse_llm_json_relaxed(ans)
    if parsed is not None:
        category = parsed.get("category", "other")
        replacement_text = parsed.get("replacement_text", "")
        out = {
            "scenario": sid,
            "round_id": round_id,
            "found": True,
            "step": step_idx,
            "agent": agent,
            "timestamp": failed_timestamp,
            "category": category,
            "suggestions": to_suggestions(category, replacement_text, ""),
            "raw": ans,
        }
    else:
        out = {
            "scenario": sid,
            "round_id": round_id,
            "found": True,
            "step": step_idx,
            "agent": agent,
            "timestamp": failed_timestamp,
            "category": "other",
            "suggestions": {},
            "raw": ans,
        }

    # 6) Save to per-round intervention file
    out_path_round = PROJECT_ROOT / "logs" / f"scenario_{sid}" / str(round_id) / f"intervention_{method}_{prompt_tmpl}.json"
    save_json(out_path_round, out)

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

