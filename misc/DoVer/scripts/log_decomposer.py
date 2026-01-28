#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from openai import AzureOpenAI
import sys
import os

AZURE_OPENAI_ENDPOINT_ENV_VAR = "AZURE_OPENAI_ENDPOINT"
DEFAULT_AZURE_OPENAI_ENDPOINT = os.environ.get(AZURE_OPENAI_ENDPOINT_ENV_VAR)

sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts.failure_proposer import build_history_path, load_problem_gt, extract_steps_from_history

PROJECT_ROOT = Path(__file__).parent.parent

SYSTEM_PROMPT = """
- You are an experienced system log analyzer and decomposer, who can effectively decompose and organize complex session logs into meaningful components.
- Your task is to analyze a session log from a Large Language Model (LLM) based agent system, and decompose the session log into a series of trials that the system had made to solve a given task.
- Refer to Section `On the LLM-based Agent System` for details about the LLM-based agent system.
- Refer to Section `On the Input Data Structure` for details on the data structure of the input logs.
- Refer to Section `Guidance for Log Decomposition` for details on how to perform the log decomposition.
- Refer to Section `On the Output Format` for details on the output data structure.

# On the LLM-based Agent System
- The LLM-based agent system can be a single or multi-agent system.
- The system is often tasked with a problem, and agents in the system work collectively to solve the task.
- Agents in the system can have different roles and responsibilities, and they may need to communicate and collaborate with others to achieve the overall goal.
- Agents work in the SEQUENTIAL manner, namely, agents are invoked one by one and no agents are executing in parallel.
- There often exists an agent playing the role of Orchestrator, who devises and updates a plan for solving the task and coordinates with the agents to solve the task.
- The general flow of the system follows the cycle of "make a plan", "execute plan", "update plan", and so on.

# On the Input Data Structure
- The input data are collected from a session in the LLM-based agent system.
- The session contains a series of interactions among agents in the system. The interaction often starts with a specific task and the goal of the system is to finish task successfully.
- The input data are in the following Json format:
{
    'problem': <problem>,
    'ground_truth_answer': <ground_truth_answer>,
    'session_logs': <session_logs>
}
- `problem` denotes the specific task that the agent system needs to solve.
- `ground_truth_answer` is the corresponding ground truth answer for the problem.
- `session_logs` provides the details of the session trace, and is a string object with the following format:
'''
    [Step 0] "agent a": "xx",
    [Step 1] "agent b": "xxxx",
    [Step 2] "agent c": "xxxxx",
    [Step 3] "agent a": "xxxxxxx"
'''
Each entry in the above represents a `Step` where an agent provides input. The 'x' symbolizes the speech/message of each agent.

# Guidance for Log Decomposition
- The goal is to decompose the session logs into a series of `Trial`s that had been made by the system.
- Each `Trial` is defined as an attempt to solve the problem, consisting of a `Planning` step and its corresponding `Execution` steps. 
- Both `Planning` and its `Execution` are manifested by `Step`s in the log.
- The `Planning` steps outline the strategy for solving the problem, while the `Execution` steps are the actual attempts made by the agents to implement the plan.
- `Planning` steps include both the initial planning and any subsequent updates to the plan.
- If `Planning` is updated in the log (e.g., due to no progress made after executing current plan), NEW `Trial` should be considered.
- The key of log decomposition is to categorize all `Step`s in the log into Four categories, `Initial_Planning`, `Update_Planning`, `Execution`, and `Others`. Refer to the following guidance for the categorization:
- `Initial_Planning` step are the step taken to create a plan for solving the problem. These steps typically involve brainstorming, outlining step-by-step strategies, and setting goals. Only ONE step in the log should be classified as `Initial_Planning`.
- `Update_Planning` steps are those that modify or refine the existing plan based on new information or feedback. These steps may involve re-evaluating the strategy, adjusting goals, or incorporating lessons learned from previous attempts. Note that the `Update_Planning` step refers to the major update of the whole task plan. The small changes of in the execution of a plan (e.g., clicking another links in the search result page when the previous link click returns no useful result) do NOT count as the `Update_Planning` step, as it is still part of a plan execution but just a different execution detail.
- Both `Initial_Planning` and `Update_Planning` steps are often carried out by the agent of the Orchestrator role. But not all `Step`s from the Orchestrator agent are `Planning` steps, as the Orchestrator agent can have responsibilities other than planning. For example, when executing a plan, the Orchestrator agent may provide instructions and guidance to other agents for better plan execution or coordination among agents.
- Not every `Initial_Planning` or `Update_Planning` step is required to be followed by `Execution` steps. This can occur if the plan is not executed or if the execution details are not captured in the log. Thus, it is acceptable to have several consective steps are labelled as `Planning` steps.
- `Others` steps are auxiliary steps that do not directly contribute to the planning or execution of the task. These may include acknowledgments of the task receival, final result collection and report result to the user, or other non-essential messages related to the core task-solving process. They often appear at the begining and end of the session logs.
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

def _make_client(azure_endpoint: str, api_version: str) -> AzureOpenAI:
    if not azure_endpoint:
        raise ValueError("Azure OpenAI endpoint is required to create a client.")
    return AzureOpenAI(azure_endpoint=azure_endpoint, api_version=api_version)

def _make_api_call(client: AzureOpenAI, model: str, messages: list, max_tokens: int) -> str:
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

    # out_dir = hist_path.parent
    # out_dir.mkdir(parents=True, exist_ok=True)
    # out_path = out_dir / f"step_scenario_{sid}_{args.model}.json"
    # with open(out_path, "w", encoding="utf-8") as f:
    #     json.dump(steps, f, ensure_ascii=False, indent=2)

    session_logs = _format_session_logs(steps)
    user_msg = {
        "problem": problem,
        "ground_truth_answer": gt,
        "session_logs": session_logs,
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_msg, ensure_ascii=False)},
    ]

    client = _make_client(args.azure_endpoint, args.api_version)
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
    out_path = out_dir / f"plan_step_scenario_{sid}_{args.model}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)

    print(str(out_path))

if __name__ == "__main__":
    main()
