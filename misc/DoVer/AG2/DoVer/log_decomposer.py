#!/usr/bin/env python3
# DoVer-specific log decomposition script.
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

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

SYSTEM_PROMPT = """
- You are an experienced system log analyzer and decomposer, who can effectively decompose and organize complex session logs into meaningful components.
- Your task is to analyze a session log from a Large Language Model (LLM) based agent system, and decompose the session log into a series of trials that the system had made to solve a given task.
- Refer to Section `On the AG2 Agent System` for details about the AG2-specific agent workflow.
- Refer to Section `On the Input Data Structure` for details on the data structure of the input logs.
- Refer to Section `Guidance for Log Decomposition` for details on how to perform the log decomposition.
- Refer to Section `On the Output Format` for details on the output data structure.

# On the AG2 Agent System
- The conversation comes from the AG2 (AutoGen 2) runtime where a `GroupChatManager` orchestrates multiple `ConversableAgent` instances.
- Agents speak strictly in sequence as the manager routes turns; there is no parallel execution.
- A typical roster includes: `Agent_Problem_Solver` (drafts multi-step reasoning), `Agent_Code_Executor` (runs Python based on solver prompts), and `Agent_Verifier` (checks and finalizes answers). Other helper agents may appear but follow the same turn-taking rules.
- The manager (`chat_manager`) issues system-level coordination messages, especially the initial etiquette message often called `chat_manner`.
- Each solver iteration follows the AG2 pattern "plan -> execute -> verify", and the manager may relaunch loops until a final verdict is reached.

# On the Input Data Structure
- The user payload is a JSON object with three keys: `problem`, `ground_truth_answer`, and `session_logs`.
- `session_logs` is a newline-separated string; each line already contains the step index and agent name in the form `[Step X] "Agent_Name": "message contents"`.
- Treat these embedded step indices as the authoritative order provided by the AG2 checkpoint.
- Step 0 typically broadcasts the problem from `Agent_Verifier` (or another task presenter). Step 1 is the `chat_manager` etiquette message describing participating agents.
- Subsequent steps (2+) capture the real problem-solving loop: planner reasoning, code execution, verification feedback, and `SOLUTION_FOUND` summaries.

# Guidance for Log Decomposition
- The goal is to decompose the AG2 session logs into a series of `Trial`s attempted by the system.
- Each `Trial` is an end-to-end loop from a high-level plan (usually spoken by `Agent_Problem_Solver`) through execution (`Agent_Code_Executor`) and verification (`Agent_Verifier` or manager follow-ups).
- The `Planning` steps outline the solver's strategy; `Execution` steps are code runs or concrete actions; verifier feedback may close the trial or trigger a new plan.
- When AG2 issues a fresh overarching strategy (often prefixed with rationale, bullet lists, or a "Let's break down" preamble), treat it as planning. If the plan changes materially after feedback, start a new trial.
- Categorize every step into `Initial_Planning`, `Update_Planning`, `Execution`, or `Others`:
  - `Initial_Planning`: the first substantive plan after setup (usually Step 2 from `Agent_Problem_Solver`). Exactly one step should receive this label.
  - `Update_Planning`: later steps where an agent revises the global approach (manager directives, solver pivoting to a new method, etc.). Only tag a step as `Update_Planning` when the speaker introduces a materially new overarching strategy or reorders the major steps; apologies, clarifications, or continuing the same approach should stay in `Others` (or remain part of the existing plan).
  - `Execution`: code blocks or action descriptions, typically spoken by `Agent_Code_Executor`, sometimes by the solver when performing calculations.
  - `Others`: setup chatter, agent introductions, `SOLUTION_FOUND` announcements, or lightweight acknowledgements that do not alter plan/execute flow.
- Signals like "SUGGESTED NEXT SPEAKER" are emitted by AG2 during coordination and usually belong to execution or verification rather than planning updates unless the underlying content changes the strategy.
- Steps 0 and 1 are typically session setup messages (task initialization and chat manner).
- Follow the below steps to decompose the session logs into `Trial`s:
- 1. Read through the `session_logs` to understand the overall context. Specifically, 
    - Understand the task and identify the set of agents has been assembled to solve the task.
    - Identify the specific roles and responsibilities of each agent in the context of the task. Identify the Orchestrator agent and how it coordinate other agents.
- 2. Categorize each `Step` in the log into `Initial_Planning`, `Update_Planning`, `Execution` and `Others` categories based on the guidance provided above.
- 3. Only output the step indices of the `Initial_Planning` and `Update_Planning` steps and the reasons for their categorization.

# On the Output Format  
- The output should be a Json object with the following structure:
{
    'initial_planning_step': {
    'step_index': <the original step index of the initial planning step, e.g., 0>,
    'reason': <the reason why this Step 0 is identified as an initial planning step>
    },
    'plan_update_steps': [
    ...,
    {
        'plan_update_step_index': <the original step index of the plan update step, e.g., 5>,
        'reason': <the reason why this Step 5 is identified as a plan update step>
    },
    ...
    ]
}
"""
def _make_client(azure_endpoint: Optional[str], api_key: Optional[str], api_version: Optional[str]):
    return make_openai_client(azure_endpoint, api_key, api_version)


def _make_api_call(client, model: str, messages: list, max_tokens: int) -> str:
    r = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, response_format={"type": "json_object"})
    return (r.choices[0].message.content or "").strip()


def _format_session_logs(steps: list) -> str:
    lines = []
    for s in steps:
        name = s.get("name", "Unknown")
        content = s.get("content", "")
        step_idx = s.get("step_idx", 0)
        lines.append(f"[Step {step_idx}] \"{name}\": {json.dumps(content, ensure_ascii=False)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Log decomposer to find planning steps and updates")
    ap.add_argument("--dataset_name", default="GSMPlus", choices=["GSMPlus", "Olympiad"], help="Dataset name (default: GSMPlus)")
    ap.add_argument("--exp_results_dir", default=None, required=True, help="Directory to save experiment results")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--hist_path", default=None, help="Path to the history file. If not provided, will be constructed from scenario and round.")
    ap.add_argument(
        "--azure-endpoint",
        default=DEFAULT_AZURE_OPENAI_ENDPOINT,
        help=f"Azure OpenAI endpoint (default from {AZURE_OPENAI_ENDPOINT_ENV_VAR} env var)",
    )
    ap.add_argument("--api-key", default=None, help="Azure OpenAI API key (defaults to AZURE_OPENAI_API_KEY env var)")
    ap.add_argument(
        "--api-version",
        default=DEFAULT_AZURE_OPENAI_API_VERSION,
        help="Azure OpenAI API version (default: %(default)s)",
    )
    ap.add_argument("--model", default="gpt-4o-20241120", choices=SUPPORTED_OPENAI_MODELS, help="Model to use (default: gpt-4o-20241120)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    args = ap.parse_args()

    if not args.azure_endpoint:
        ap.error(
            f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
        )

    dataset_name = args.dataset_name.strip()
    assert dataset_name == "GSMPlus", "Only GSMPlus dataset is supported currently"

    exp_results_dir = Path(args.exp_results_dir)
    assert exp_results_dir.exists(), f"Experiment results directory not found: {str(exp_results_dir)}"

    sid = args.scenario.strip()
    hist_path = Path(args.hist_path) if args.hist_path is not None else exp_results_dir / f"{sid}" / f"chat_history.json"
    if not hist_path.exists():
        print(json.dumps({"scenario": sid, "error": f"history not found: {str(hist_path)}"}, ensure_ascii=False))
        return
    
    with open(hist_path, "r", encoding="utf-8") as f:
        history_data = json.load(f)
    assert 'chat_history' in history_data, f"chat_history not found in {str(hist_path)}"
    steps = history_data['chat_history']
    for i, s in enumerate(steps):
        s['step_idx'] = i  # add step index    
    session_logs = _format_session_logs(steps)

    # Save chat history with step indices
    out_dir = hist_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"chat_history_with_index.json"
    if not out_path.exists():
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(steps, f, ensure_ascii=False, indent=2)

    problem, gt = load_problem_gt(exp_results_dir, sid)
    user_msg = {
        "problem": problem,
        "ground_truth_answer": gt,
        "session_logs": session_logs,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_msg, ensure_ascii=False)},
    ]

    client = _make_client(args.azure_endpoint, args.api_key, args.api_version)
    raw = _make_api_call(client, args.model, messages, args.max_tokens)

    try:
        result_obj = json.loads(raw)
    except Exception:
        print(json.dumps({"scenario": sid, "error": "model did not return valid JSON", "raw": raw[:1000]}, ensure_ascii=False))
        return

    ts_map = {int(s["step_idx"]): s.get("timestamp") for s in steps}
    for u in result_obj.get("plan_update_steps", []):
        idx = u.get("plan_update_step_index")
        if isinstance(idx, str):
            try:
                idx = int("".join(ch for ch in idx if ch.isdigit()))
            except Exception:
                idx = None
        if isinstance(idx, int):
            u["plan_update_step_timestamp"] = ts_map.get(idx)

    out_dir = hist_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"plan_step.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)

    print(str(out_path))


if __name__ == "__main__":
    main()
