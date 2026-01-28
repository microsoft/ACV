#!/usr/bin/env python3
# Trial summarizer tailored for DoVer workflows.

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
- You are an experienced system log analyzer and summarizer, who can effectively analyze and summarize complex session logs into concise insights.
- Your task is to analyze a partial session log related to a trial to solve a given task in a Large Language Model (LLM) based agent system, and summarize the key process of the trial as well as perform root cause analysis of the trial if it is a failed trial. 
- Refer to Section `On the AG2 Agent System` for the background knowledge about the AG2 conversation runtime.
- Refer to Section `On the Trial and Session Log Decomposition` for the background knowledge about log of a session and how the prior process of decomposing the whole session log into different trials.
- Refer to Section `On the Input Data Structure` for details on the input data for the current trial summarization task.
- Refer to Section `Guidance for Trial Summarization` for details on how to perform the log analysis and trial summarization.
- Refer to Section `On the Output Format` for details on the output data structure.

- The AG2 manager routes turns sequentially; there is no parallel speaking. A typical roster is: `Agent_Problem_Solver` (strategic reasoning), `Agent_Code_Executor` (Python execution), `Agent_Verifier` (checks outcomes), plus the `chat_manager` issuing orchestration messages like the "chat_manner" introduction.
- Conversation loops follow the AG2 pattern "plan -> execute -> verify" until a `SOLUTION_FOUND` or failure condition is declared.

# On the Trial and Session Log Decomposition
- The input trial log data are taken from an AG2 session where the full conversation has already been split into trials.
- Each entry in `session_logs` follows the canonical `[Step i] "Agent_Name": "message"` pattern (detailed again in the input section) and corresponds to a single AG2 agent turn in chronological order.
- The whole session log had been decomposed into different `Trial`s with the following requirements:
- Each `Trial` is defined as an attempt to solve the problem, consisting of a `Planning` step and its corresponding `Execution` steps. 
- Both `Planning` and its `Execution` are manifested by `Step`s in the log.
- The `Planning` steps outline the strategy for solving the problem, while the `Execution` steps are the actual attempts made by the agents to implement the plan.
- `Planning` steps include both the initial planning and any subsequent updates to the plan.
- Going through the session log, if there is a step related to plan update (e.g., due to no progress made after executing the existing plan), the existing `Trial` would terminate and a new `Trial` would be considered to start.
- The decomposition of the session log into `Trial`s allows for a more granular analysis of the agent system's behavior and performance.

# On the Input Data Structure
- The input data are in the following Json format:
{
    'problem': <problem>,
    'ground_truth_answer': <ground_truth_answer>,
    'previous_trial_summary': [
    ...,
    {
        'trial_index': <trial_index>,
        'trial_plan': <trial_plan>,
        'trial_execution': <trial_execution>,
        'is_succeed': <is_succeed>,
        'trial_summary': <trial_summary>
    },
    ...
    ],
    'trial_logs_to_summarize': <trial_logs_to_summarize>,
    }
}
- `problem` denotes the specific task that the AG2 agents need to solve.
- `ground_truth_answer` is the target answer for the problem.
- `previous_trial_summary` lists prior trial outcomes (if any). Each element includes `trial_index`, `trial_plan`, `trial_execution`, `is_succeed`, and `trial_summary` / `trial_overall_summary`, mirroring what the summarizer produced for earlier trials. For the very first trial this list is empty.
- `trial_logs_to_summarize` is a newline-separated string covering only the steps within the current trial segment, formatted like the example above with embedded step indices and agent names.
- Example:
    ```
    [Step n] "agent a": "xx",
    [Step n+1] "agent b": "xxxx",
    ...
    [Step m] "agent c": "xxxxxxx"
    ```
The initial step of the trial, (i.e., `Step n`) often refers to the above `Planning` step, involving an initial plan creation or update, and the following steps belong to the execution of the plan of this trial.

# Guidance for Trial Summarization
- The goal is to summarize the provided `trial_logs_to_summarize` based on the overall context including the task and previous trial history.
- Follow the below steps for trial summarization:
- 1. Read through the `problem` and `ground_truth_answer` to understand the task and its ground truth answer.
- 2. Before inspecting any trial logs, restate the problem in your own words, enumerate all hard constraints (units, integer requirements, bounds), and compute any deterministic invariants. Treat these notes as the baseline when later evaluating plan/execution steps and trace whether mistakes stem from violating these constraints rather than raw calculation errors.
- 3. Read through the `previous_trial_summary` to understand how agents try to solve the task in previous trials.
- 4. Examine the `trial_logs_to_summarize` to understand the specific steps taken in the current trial. Specifically,
    - Understand the first planning step of the current trial. If it involves a plan update, you need to derive the reasoning behind the update by considering the `trial_plan` and `trial_summary` of the last trial.
    - Closely track the execution steps after the planning step of the current trial and examine how they carry out the plan and solve the task. Note that there can be NO execution steps after the planning step, e.g., due to no execution in reality.
    - Pay high attention to the final outcome of the trial, especially whether it successfully solve the task or not. If succeed, please reflect how and why this trial solves the task successfully, and compare its success with the prior failed trials. If not, please reflect why it fails and which mistake agents and steps are responsible for the failure.
    - Rigorously verify every decisive calculation or logical deduction that appears in the logs. Re-run the arithmetic or algebra yourself, use the provided `ground_truth_answer` only as an evaluation reference for your summary, and flag any mismatch explicitly.
    - When the constraints you derived in Step 2 conflict with what the agents are assuming, diagnose this as a problem-understanding/root-cause issue; clearly state why the assumption is invalid before discussing any numerical slip.
    - Whenever you detect a numerical or logical discrepancy, cite the earliest `step_idx` where it appears, briefly describe the incorrect assumption/value, and give the corrected result in one concise sentence. Focus on pinpointing the root cause; leave detailed fix steps to downstream intervention components, and keep recommendations limited to checks agents could have performed with data already in the log.
    - If the current trial segment contains the final answer or `SOLUTION_FOUND` verdict, restate it and cross-check against your own recomputation (using the problem statement and, if needed, the `ground_truth_answer`). If that verdict is missing because the trial cuts off earlier, simply note that no final answer appears within the provided steps and base your assessment on the available context.
- 5. Output the trial summary with the following key components:
    - `trial_context`: the context in which the trial was conducted, including relevant information from previous trials and the current task.
    - `trial_plan`: a detailed plan for the current trial. The plan should be self-contained, namely, if the original log at the plan step only contains the plan update part, you should derive the missing context from the previous trial's plan and summary. Output the plan in the step-by-step format and number them for the progress tracking, e.g., ["1. xxx", "2. xxx", ...].
    - `trial_execution`: a detailed description of the execution process during the CURRENT trial, NOT the whole session. Only extract execution details from the logs given in the current trial logs (`trial_logs_to_summarize`). NEVER quote execution details from prior trials. If no execution details can be found after the planning step in the current trial (e.g., due to no execution in reality), directly output "No execution details found".
    - `plan_fulfillment_status`: summarize the plan fulfillment status based on `trial_execution` and `trial_plan`. You need to map the progress from execution to the numbered planned steps in `trial_plan`. Namely, output the plan fulfillment status as a json object:
    {
        "fully_fulfilled_plan_steps": [<plan_step_index>],
        "partially_fulfilled_plan_steps": [<plan_step_index>],
        "unfulfilled_plan_steps": [<plan_step_index>]
    }
    Note that `<plan_step_index>` refers to the plan step index in `trial_plan`, not the step index in the original session logs.
    - `is_succeed`: set to `true` only when both the AG2 verdict (e.g., `SOLUTION_FOUND`) indicates success and your independent recomputation or `ground_truth_answer` check confirms the reported answer; otherwise, output `false`.
    - `trial_reflection`: a reflection on the trial's outcomes, including what worked well, what didn't, and any insights gained for future trials.
    - `mistake_agent`: only required for failed trials. Identify which agent is mainly responsible for the trial failure. If multiple agents are responsible, only choose the most relevant one.
    - `mistake_step_index`: only required for failed trials. Identify the specific step in the trial where the mistake occurred.
    - `mistake_reason`: only required for failed trials. Explain why you choose the mistake agent and step, and explicitly state the incorrect result, the corrected calculation, and how the discrepancy diverges from the ground truth.
    - 'trial_overall_summary': a summary of the trial's overall performance, including key process, successes and failures.

# On the Output Format
- The output should be a Json object with the following structure:
{
    'trial_context': <the context in which the trial was conducted. Object Type: string>,
    'trial_plan': <a detailed plan for the current trial. Object Type: list of string>,
    'trial_execution': <a detailed description of the execution process and progress made during the trial. Output "No execution details found" if no execution steps after the planning step. Object Type: string>,
    'trial_progress': {
    "fully_fulfilled_plan_steps": [<plan_step_index, Object Type: int>],
    "partially_fulfilled_plan_steps": [<plan_step_index, Object Type: int>],
    "unfulfilled_plan_steps": [<plan_step_index, Object Type: int>]
    },
    'is_succeed': <whether the current trial successfully solves the task or not. Object Type: boolean>,
    'trial_reflection': <a reflection on the trial's outcomes. Object Type: string>,
    'mistake_agent': <the agent mainly responsible for the trial failure, if applicable. Object Type: string>,
    'mistake_step_index': <the specific step in the trial where the mistake occurred, if applicable. Object Type: int>,
    'mistake_reason': <an explanation of why the identified agent and step are considered mistakes, explicitly calling out whether the root cause is a misunderstanding of the problem constraints/invariants or a pure execution error, and referencing the constraint notes from Step 2. Object Type: string>,
    'trial_overall_summary': <a summary of the trial's overall performance, including key process, successes and failures. Object Type: string>
}
"""
def _make_client(azure_endpoint: Optional[str], api_key: Optional[str], api_version: Optional[str]):
    return make_openai_client(azure_endpoint, api_key, api_version)


def _make_api_call(client, model: str, messages: list, max_tokens: int) -> str:
    r = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, response_format={"type": "json_object"})
    return (r.choices[0].message.content or "").strip()


def _format_segment(steps, start_idx: int, end_idx: int) -> str:
    lines = []
    for s in steps:
        i = s.get("step_idx", 0)
        if start_idx <= i <= end_idx:
            lines.append(f"[Step {i}] \"{s.get('name','Unknown')}\": {json.dumps(s.get('content',''), ensure_ascii=False)}")
    return "\n".join(lines)


def _coerce_int(x):
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        d = "".join(ch for ch in x if ch.isdigit())
        return int(d) if d else None
    return None


def main():
    ap = argparse.ArgumentParser(description="Trial summarizer by plan updates")
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
    hist_path = Path(args.hist_path) if args.hist_path is not None else exp_results_dir / f"{sid}" / f"chat_history_with_index.json"
    if not hist_path.exists():
        print(json.dumps({"scenario": sid, "error": f"history not found: {str(hist_path)}, you may run `log_decomposition` first."}, ensure_ascii=False))
        return

    with open(hist_path, "r", encoding="utf-8") as f:
        steps = json.load(f)
    assert len(steps) > 0, f"No steps found in history: {str(hist_path)}"

    plan_path = hist_path.parent / f"plan_step.json"
    if not plan_path.exists():
        print(json.dumps({"scenario": sid, "error": f"plan step json not found: {str(plan_path)}"}, ensure_ascii=False))
        return
    plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))

    starts = []
    init_idx = _coerce_int(plan_obj.get("initial_planning_step", {}).get("step_index"))
    if init_idx is not None:
        starts.append(init_idx)
    for u in plan_obj.get("plan_update_steps", []):
        k = _coerce_int(u.get("plan_update_step_index"))
        if k is not None:
            starts.append(k)
    starts = sorted(set(starts))
    if not starts:
        starts = [0]

    last_idx = steps[-1]["step_idx"]
    bounds = []
    for i, sidx in enumerate(starts):
        eidx = (starts[i + 1] - 1) if i + 1 < len(starts) else last_idx
        if sidx <= eidx:
            bounds.append((i, sidx, eidx))

    client = _make_client(args.azure_endpoint, args.api_key, args.api_version)

    summaries = []
    prev_list = []

    problem, gt = load_problem_gt(exp_results_dir, sid)
    for trial_index, sidx, eidx in bounds:
        seg = _format_segment(steps, sidx, eidx)
        payload = {
            "problem": problem,
            "ground_truth_answer": gt,
            "previous_trial_summary": prev_list,
            "trial_logs_to_summarize": seg,
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        raw = _make_api_call(client, args.model, messages, args.max_tokens)
        try:
            obj = json.loads(raw)
        except Exception:
            print(json.dumps({"scenario": sid, "trial_index": trial_index, "error": "model did not return valid JSON", "raw": raw[:1000]}, ensure_ascii=False))
            return
        m_idx = _coerce_int(obj.get("mistake_step_index"))
        obj["trial_index"] = trial_index
        obj["separator"] = f"######### Trial Index {trial_index} (Steps: {sidx} - {eidx}) #########"
        summaries.append(obj)
        prev_list.append({
            "trial_index": trial_index,
            "trial_plan": obj.get("trial_plan", []),
            "trial_execution": obj.get("trial_execution", ""),
            "is_succeed": obj.get("is_succeed", False),
            "trial_summary": obj.get("trial_overall_summary", "")
        })

    out_path = hist_path.parent / f"trial_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(str(out_path))


if __name__ == "__main__":
    main()
