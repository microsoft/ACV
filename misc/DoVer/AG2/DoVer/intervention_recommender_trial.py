#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

try:
    from const import SUPPORTED_OPENAI_MODELS
    from utils import (
        AZURE_OPENAI_ENDPOINT_ENV_VAR,
        DEFAULT_AZURE_OPENAI_ENDPOINT,
        DEFAULT_AZURE_OPENAI_API_VERSION,
        load_problem_gt,
        make_openai_client,
    )
except ModuleNotFoundError:
    if str(CURRENT_DIR) not in sys.path:
        sys.path.append(str(CURRENT_DIR))
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.append(str(PROJECT_ROOT))
    from const import SUPPORTED_OPENAI_MODELS
    from utils import (
        AZURE_OPENAI_ENDPOINT_ENV_VAR,
        DEFAULT_AZURE_OPENAI_ENDPOINT,
        DEFAULT_AZURE_OPENAI_API_VERSION,
        load_problem_gt,
        make_openai_client,
    )


def _make_client(azure_endpoint: Optional[str], api_key: Optional[str], api_version: Optional[str]):
    return make_openai_client(azure_endpoint, api_key, api_version)


def _chat_once(
    client,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return (resp.choices[0].message.content or "").strip()


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        body = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(body).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


def _load_steps(scenario_dir: Path) -> List[Dict[str, Any]]:
    source_path = scenario_dir / "chat_history_with_index.json"
    if not source_path.exists():
        source_path = scenario_dir / "chat_history.json"
    if not source_path.exists():
        raise FileNotFoundError("chat history file not found")
    if source_path.name == "chat_history.json":
        data = json.loads(source_path.read_text(encoding="utf-8"))
        steps = data.get("chat_history") or []
    else:
        steps = json.loads(source_path.read_text(encoding="utf-8"))
    normalized: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps):
        item = dict(step)
        step_idx = item.get("step_idx", idx)
        try:
            step_idx = int(step_idx)
        except (TypeError, ValueError):
            step_idx = idx
        item["step_idx"] = step_idx
        if not item.get("name") and item.get("role"):
            item["name"] = item["role"]
        normalized.append(item)
    return normalized


def _trial_context_window(
    steps: List[Dict[str, Any]],
    fail_idx: int,
    window: int = 2,
) -> List[Dict[str, Any]]:
    if fail_idx is None or fail_idx < 0 or fail_idx >= len(steps):
        return []
    start = max(0, fail_idx - max(window, 0))
    end = min(len(steps) - 1, fail_idx)
    context: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        s = steps[idx]
        context.append(
            {
                "idx": idx,
                "name": s.get("name", ""),
                "content": s.get("content", ""),
                "role": s.get("role"),
            }
        )
    return context


def _coerce_int(val: Any) -> Optional[int]:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        digits = "".join(ch for ch in val if ch.isdigit())
        if digits:
            return int(digits)
    return None


def _build_prior_trials_summary(
    trials: List[Dict[str, Any]],
    current_index: Optional[int],
    max_trials: int,
) -> str:
    if current_index is None:
        current_index = 10**9
    history: List[str] = []
    for trial in trials:
        idx = _coerce_int(trial.get("trial_index"))
        if idx is None or idx >= current_index:
            continue
        summary = trial.get("trial_overall_summary") or ""
        history.append(f"Trial {idx}: {summary}")
    if not history:
        return ""
    return "\n".join(history[-max_trials:])


def _format_progress(progress: Optional[Dict[str, Any]]) -> str:
    if not isinstance(progress, dict) or not progress:
        return "N/A"
    fully = progress.get("fully_fulfilled_plan_steps") or []
    partially = progress.get("partially_fulfilled_plan_steps") or []
    unfulfilled = progress.get("unfulfilled_plan_steps") or []
    return (
        f"Fully fulfilled: {fully}\n"
        f"Partially fulfilled: {partially}\n"
        f"Unfulfilled: {unfulfilled}"
    )


def _build_intervention_prompt(
    problem: str,
    ground_truth: str,
    current_trial: Dict[str, Any],
    context_window: List[Dict[str, Any]],
    prior_trials_summary: str,
) -> str:
    trial_index = current_trial.get("trial_index")
    plan = current_trial.get("trial_plan") or []
    if isinstance(plan, list):
        plan_text = "\n".join(str(p) for p in plan) or "N/A"
    else:
        plan_text = str(plan)
    progress_text = _format_progress(current_trial.get("trial_progress"))
    ctx_lines = [
        f"[Step {c['idx']}] {c.get('name','')}: {c.get('content','')}"
        for c in context_window
    ]
    ctx_block = "\n".join(ctx_lines) or "No surrounding steps captured."
    fail_idx = current_trial.get("mistake_step_index")
    agent = current_trial.get("mistake_agent") or ""
    reason = current_trial.get("mistake_reason") or current_trial.get("trial_overall_summary") or ""
    trial_context = current_trial.get("trial_context") or ""
    execution = current_trial.get("trial_execution") or ""
    reflection = current_trial.get("trial_reflection") or ""
    overall = current_trial.get("trial_overall_summary") or ""
    ground_truth_text = ground_truth if ground_truth else "N/A"
    prior_text = prior_trials_summary or "No prior trials."
    return (
        "You are an expert in debugging multi-agent systems. A failure analyzer has examined a AG2 system execution and located a problematic step. "
        "Use this as guidance to design a precise, minimal intervention that eliminates the root cause.\n\n"
        "## Task Background\n"
        f"Original task: {problem}\n"
        f"Reference answer (for evaluator guidance only; NEVER reveal it to the agents or cite the numeric value directly): {ground_truth_text}\n\n"
        "The overall path has been split into multiple trials. Below are summaries of previous trials:\n"
        f"{prior_text}\n\n"
        "Here are the details of the current trial:\n"
        f"Trial index: {trial_index}\n"
        f"Context: {trial_context}\n"
        f"Plan:\n{plan_text}\n\n"
        f"Execution:\n{execution}\n\n"
        f"Progress:\n{progress_text}\n\n"
        f"Reflection:\n{reflection}\n\n"
        f"Overall summary:\n{overall}\n\n"
        "Specific Details\n"
        f"Failed step index: {fail_idx}\n"
        f"Failed agent: {agent}\n"
        f"Diagnosed reason: {reason}\n\n"
        "## Execution Context\n"
        "Below are the two steps immediately before the failure and the failed step itself:\n"
        f"{ctx_block}\n\n"
        "## System specifics and intervention policy:\n"
        f"- Compose a full replacement message for {agent or 'the failed agent'} at Step {fail_idx}. Write it as if this agent is now delivering the corrected reasoning rather than giving themselves instructions.\n"
        f"- Restate the necessary equations, constraints, or code so the message stands on its own. Do not say \"recompute\" or \"redo\"—instead, directly show the corrected computation or explanation.\n"
        f"- You may rely on lessons learned later in the trial to refine this response—e.g., adjusting formulas, tightening invariants, or fixing code—but do not reference step numbers beyond {fail_idx}. Blend those insights into the rewritten reasoning so it feels native to this turn.\n"
        "- Treat the reference answer as internal validation only; never restate its numeric value or instruct agents to \"match the ground truth\". Demonstrate the reasoning that leads to the corrected result using only task constraints.\n"
        "- Explicitly note the faulty assumption or calculation from the original turn, then walk through the corrected steps within the same message so the conversation can continue seamlessly.\n"
        "- Use declarative, procedural language (e.g., “Compute the usable length as …, subtract … each day, stop once …”) rather than reflective phrasing like “I realized …”.\n"
        "- Use plain ASCII text only; avoid invisible control characters or markdown fences that could pollute the injected message.\n\n"
        "Return STRICT JSON with the following schema:\n"
        "{\n"
        "  \"replacement_text\": \"the exact rewritten message for the specified agent\"\n"
        "}\n"
        "Respond with JSON only, no extra commentary."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AG2 trial-level intervention recommender")
    parser.add_argument("--dataset_name", default="GSMPlus", choices=["GSMPlus", "Olympiad"])
    parser.add_argument("--exp_results_dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument(
        "--azure-endpoint",
        default=DEFAULT_AZURE_OPENAI_ENDPOINT,
        help=f"Azure OpenAI endpoint (default from {AZURE_OPENAI_ENDPOINT_ENV_VAR} env var)",
    )
    parser.add_argument("--api-key", default=None, help="Azure OpenAI API key (defaults to AZURE_OPENAI_API_KEY env var)")
    parser.add_argument(
        "--api-version",
        default=DEFAULT_AZURE_OPENAI_API_VERSION,
        help="Azure OpenAI API version (default: %(default)s)",
    )
    parser.add_argument("--model", default="gpt-4o-20241120", choices=SUPPORTED_OPENAI_MODELS)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--output", default=None, help="Optional output path for interventions json")
    args = parser.parse_args()

    if not args.azure_endpoint:
        parser.error(
            f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
        )

    exp_dir = Path(args.exp_results_dir).expanduser().resolve()
    sid = str(args.scenario).strip()
    scenario_dir = exp_dir / sid
    if not scenario_dir.exists():
        print(json.dumps({"scenario": sid, "error": f"scenario path not found: {scenario_dir}"}, ensure_ascii=False))
        return

    try:
        steps = _load_steps(scenario_dir)
    except FileNotFoundError as exc:
        print(json.dumps({"scenario": sid, "error": str(exc)}, ensure_ascii=False))
        return

    trial_summary_path = scenario_dir / "trial_summary.json"
    if not trial_summary_path.exists():
        print(json.dumps({"scenario": sid, "error": f"trial summary not found: {trial_summary_path}"}, ensure_ascii=False))
        return
    trials = json.loads(trial_summary_path.read_text(encoding="utf-8"))

    try:
        problem, ground_truth = load_problem_gt(exp_dir, sid)
    except FileNotFoundError as exc:
        print(json.dumps({"scenario": sid, "error": str(exc)}, ensure_ascii=False))
        return

    outputs: List[Dict[str, Any]] = []
    client = _make_client(args.azure_endpoint, args.api_key, args.api_version)

    for trial in trials:
        if bool(trial.get("is_succeed")):
            continue
        fail_idx = _coerce_int(trial.get("mistake_step_index"))
        if fail_idx is None or fail_idx < 0 or fail_idx >= len(steps):
            continue
        context_window = _trial_context_window(steps, fail_idx)
        current_index = _coerce_int(trial.get("trial_index"))
        prior_summary = _build_prior_trials_summary(trials, current_index, max_trials=3)
        prompt = _build_intervention_prompt(
            problem,
            ground_truth,
            trial,
            context_window,
            prior_summary,
        )
        assert client is not None
        raw = _chat_once(
            client,
            args.model,
            [
                {"role": "system", "content": "You produce minimal, targeted interventions for AG2 multi-agent transcripts."},
                {"role": "user", "content": prompt},
            ],
            args.max_tokens,
        )
        parsed = _safe_json_loads(raw)
        replacement_text = (
            parsed.get("replacement_text")
            or parsed.get("agent_follow_up")
            or parsed.get("plan_patch")
            or parsed.get("chat_manager_instruction")
            or ""
        )
        replacement_text = replacement_text.strip()
        if not replacement_text:
            continue
        outputs.append(
            {
                "scenario": sid,
                "trial_index": trial.get("trial_index"),
                "step": fail_idx,
                "agent": trial.get("mistake_agent") or steps[fail_idx].get("name", "unknown"),
                "replacement_text": replacement_text,
                "raw": raw,
            }
        )

    out_path = Path(args.output).expanduser().resolve() if args.output else scenario_dir / f"intervention_recommendation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
