#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from openai import AzureOpenAI
import os

AZURE_OPENAI_ENDPOINT_ENV_VAR = "AZURE_OPENAI_ENDPOINT"
DEFAULT_AZURE_OPENAI_ENDPOINT = os.environ.get(AZURE_OPENAI_ENDPOINT_ENV_VAR)

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.failure_proposer import build_history_path, load_problem_gt, extract_steps_from_history

PROJECT_ROOT = Path(__file__).parent.parent
SYSTEM_PROMPT = """
- You are an experienced system log analyzer and summarizer, who can effectively analyze and summarize complex session logs into concise insights.
- Your task is to analyze a partial session log related to a trial to solve a given task in a Large Language Model (LLM) based agent system, and summarize the key process of the trial as well as perform root cause analysis of the trial if it is a failed trial. 
- Refer to Section `On the LLM-based Agent System` for the background knowledge about the LLM-based agent system.
- Refer to Section `On the Trial and Session Log Decomposition` for the background knowledge about log of a session and how the prior process of decomposing the whole session log into different trials.
- Refer to Section `On the Input Data Structure` for details on the input data for the current trial summarization task.
- Refer to Section `Guidance for Trial Summarization` for details on how to perform the log analysis and trial summarization.
- Refer to Section `On the Output Format` for details on the output data structure.

# On the LLM-based Agent System
- The LLM-based agent system can be a single or multi-agent system.
- The system is often tasked with a problem, and agents in the system work collectively to solve the task.
- Agents in the system can have different roles and responsibilities, and they may need to communicate and collaborate with others to achieve the overall goal.
- Agents work in the SEQUENTIAL manner, namely, agents are invoked one by one and no agents are executing in parallel.
- There often exists an agent playing the role of Orchestrator, who devises and updates a plan for solving the task and coordinates with the agents to solve the task.
- The general flow of the system follows the cycle of "make a plan", "execute plan", "update plan", and so on.

# On the Trial and Session Log Decomposition
- The input trial log data are part of a session in the LLM-based agent system.
- The session contains a series of interactions among agents in the system. The interaction often starts with a specific task and the goal of the system is to finish task successfully.
- The whole log of the session (`session_logs`) is structured as the step-by-step messages from agents, namely,
'''
[Step 0] "agent a": "xx",
[Step 1] "agent b": "xxxx",
[Step 2] "agent c": "xxxxx",
[Step 3] "agent a": "xxxxxxx"
'''
Each entry in the above represents a `Step` where an agent provides input. The 'x' symbolizes the speech/message of each agent.
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
- `problem` denotes the specific task that the agent system needs to solve.
- `ground_truth_answer` is the corresponding ground truth answer for the problem.
- `previous_trial_summary` provides the history of all previous trials in the session. Each element corresponds to each historical trial, including their `trial_index`, `trial_plan` (i.e., step by step plan for the trial), `trial_execution` (i.e., execution details for the trial), `trial_summary` and the indicator of 'is_succeed' to denote whether the trial successfully solves the task or not. Empty list for the first trial.
- `trial_logs_to_summarize` provides the log details related to the trial intended to be summarized. It still follows the above step-by-step style of `session_logs` but only contains the steps related to the specific trial.
'''
    [Step n] "agent a": "xx",
    [Step n+1] "agent b": "xxxx",
    ...
    [Step m] "agent c": "xxxxxxx"
'''
The initial step of the trial, (i.e., `Step n`) often refers to the above `Planning` step, involving an initial plan creation or update, and the following steps belong to the execution of the plan of this trial.

# Guidance for Trial Summarization
- The goal is to summarize the provided `trial_logs_to_summarize` based on the overall context including the task and previous trial history.
- Follow the below steps for trial summarization:
- 1. Read through the `problem` and `ground_truth_answer` to understand the task and its ground truth answer.
- 2. Read through the `previous_trial_summary` to understand how agents try to solve the task in previous trials.
- 3. Examine the `trial_logs_to_summarize` to understand the specific steps taken in the current trial. Specifically,
    - Understand the first planning step of the current trial. If it involves a plan update, you need to derive the reasoning behind the update by considering the `trial_plan` and `trial_summary` of the last trial.
    - Closely track the execution steps after the planning step of the current trial and examine how they carry out the plan and solve the task. Note that there can be NO execution steps after the planning step, e.g., due to no execution in reality.
    - Pay high attention to the final outcome of the trial, especially whether it successfully solve the task or not. If succeed, please reflect how and why this trial solves the task successfully, and compare its success with the prior failed trials. If not, please reflect why it fails and which mistake agents and steps are responsible for the failure. 
- 4. Output the trial summary with the following key components:
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
    - `is_succeed`: whether the current trial successfully solves the task or not.
    - `trial_reflection`: a reflection on the trial's outcomes, including what worked well, what didn't, and any insights gained for future trials.
    - `mistake_agent`: only required for failed trials. Identify which agent is mainly responsible for the trial failure. If multiple agents are responsible, only choose the most relevant one.
    - `mistake_step_index`: only required for failed trials. Identify the specific step in the trial where the mistake occurred.
    - `mistake_reason`: only required for failed trials. Explain why you choose the mistake agent and step.
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
    'mistake_reason': <an explanation of why the identified agent and step are considered mistakes, if applicable. Object Type: string>,
    'trial_overall_summary': <a summary of the trial's overall performance, including key process, successes and failures. Object Type: string>
}
"""

def _make_client(azure_endpoint: str, api_version: str) -> AzureOpenAI:
    if not azure_endpoint:
        raise ValueError("Azure OpenAI endpoint is required to create a client.")
    return AzureOpenAI(azure_endpoint=azure_endpoint, api_version=api_version)

def _make_api_call(client: AzureOpenAI, model: str, messages: list, max_tokens: int) -> str:
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
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--round", default="1")
    ap.add_argument("--hist_path", default=None, help="Path to the history file. If not provided, will be constructed from scenario and round.")
    ap.add_argument(
        "--azure-endpoint",
        default=DEFAULT_AZURE_OPENAI_ENDPOINT,
        help="Azure OpenAI endpoint (default from AZURE_OPENAI_ENDPOINT env var)",
    )
    ap.add_argument("--api-version", default="2024-08-01-preview")
    ap.add_argument("--model", default="gpt-4o", help="Model to use (default: gpt-4o)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    args = ap.parse_args()
    if not args.azure_endpoint:
        ap.error(
            f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
        )

    sid = args.scenario.strip()
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

    plan_path = hist_path.parent / f"plan_step_scenario_{sid}_{args.model}.json"
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

    client = _make_client(args.azure_endpoint, args.api_version)

    summaries = []
    prev_list = []

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
        if isinstance(m_idx, int):
            obj["mistake_step_timestamp"] = ts_map.get(m_idx)
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

    out_path = hist_path.parent / f"trial_summary_scenario_{sid}_{args.model}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(str(out_path))

if __name__ == "__main__":
    main()
