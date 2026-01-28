#!/usr/bin/env python3
"""
Batch Milestone Evaluation Script

This script evaluates session logs against ground truth milestones for all scenarios
in logs_dki09 directory across specified rounds (5, 6, 7).

Usage:
    python scripts/batch_milestone_evaluation.py [--dry-run] [--scenarios scenario_list] [--rounds round_list]

Example:
    python scripts/batch_milestone_evaluation.py --scenarios "[3, 5, 9]" --rounds "[5, 6]"
"""

import pandas as pd
import json
import yaml
import time
from tqdm import tqdm
import os
import traceback
import argparse
from pathlib import Path

from openai import AzureOpenAI

AZURE_OPENAI_ENDPOINT_ENV_VAR = "AZURE_OPENAI_ENDPOINT"
DEFAULT_AZURE_OPENAI_ENDPOINT = os.environ.get(AZURE_OPENAI_ENDPOINT_ENV_VAR)

def _make_api_call(client, model, messages, max_tokens, response_format={"type":"text"}):
    """Makes an API call to Azure OpenAI with simple retry on 429 rate limit."""
    max_retries = 5
    base_wait = 3  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            if "gpt-5" or "gpt-o3" or "gpt-o4-mini" in model:
                response = client.chat.completions.create(
                    model=model, 
                    messages=messages, 
                    max_completion_tokens=max_tokens, 
                    response_format=response_format
                )
                return (response.choices[0].message.content or "").strip()
            response = client.chat.completions.create(
                model=model, 
                messages=messages, 
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "rate limit" in err_msg.lower():
                wait_s = base_wait * attempt
                print(f"Rate limit hit (attempt {attempt}/{max_retries}). Waiting {wait_s}s before retrying...")
                time.sleep(wait_s)
                continue
            else:
                print(f"Error during OpenAI API call: {e}")
                return None
    print("Error during OpenAI API call: exceeded retries due to rate limiting.")
    return None

def _coerce_int(x):
    """Convert various input types to integer."""
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        d = "".join(ch for ch in x if ch.isdigit())
        return int(d) if d else None
    return None

def _get_trial_bounds(plan_obj, steps):
    """Extract trial boundaries from plan object and steps."""
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

    return bounds

def load_gt_milestones(gt_milestone_fp):
    """Load ground truth milestone data from JSONL file."""
    gt_milestone_data = []
    if not os.path.exists(gt_milestone_fp):
        print(f"Ground truth milestone file not found: {gt_milestone_fp}")
        return gt_milestone_data
    
    with open(gt_milestone_fp, "r", encoding='utf-8') as f:
        for line in f:
            try:
                gt_milestone_data.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"JSON decode error in gt milestone file: {e}")
                continue
    
    print(f"Loaded {len(gt_milestone_data)} ground truth milestone entries")
    return gt_milestone_data

def load_prompt_template(prompt_tmpl_fp):
    """Load the milestone evaluator prompt template."""
    if not os.path.exists(prompt_tmpl_fp):
        print(f"Prompt template file not found: {prompt_tmpl_fp}")
        return None
    
    with open(prompt_tmpl_fp, "r", encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_scenario_directories(base_dir, target_scenarios=None):
    """Get list of scenario directories to process."""
    if not os.path.exists(base_dir):
        print(f"Base directory not found: {base_dir}")
        return []
    
    scenario_dirs = []
    for item in os.listdir(base_dir):
        if item.startswith("scenario_") and os.path.isdir(os.path.join(base_dir, item)):
            scenario_id = item.split("_")[-1]
            try:
                scenario_num = int(scenario_id)
                if target_scenarios is None or scenario_num in target_scenarios:
                    scenario_dirs.append((scenario_num, os.path.join(base_dir, item)))
            except ValueError:
                continue
    
    scenario_dirs.sort(key=lambda x: x[0])  # Sort by scenario number
    return scenario_dirs

def process_scenario_round(scenario_dir, scenario_id, round_num, gt_milestone_data, 
                          prompt_tmpl, client, model, dry_run=False):
    """Process a single scenario-round combination."""
    round_dir = os.path.join(scenario_dir, str(round_num))
    
    if not os.path.exists(round_dir):
        print(f"Round directory not found: {round_dir}")
        return False
    
    # Find required files
    step_json_fp = None
    plan_step_fp = None
    
    for f in os.listdir(round_dir):
        if f.startswith("step_scenario_") and f.endswith(".json"):
            step_json_fp = f
        elif f.startswith("plan_step_scenario_") and f.endswith(".json"):
            plan_step_fp = f
    
    if step_json_fp is None:
        print(f"Step JSON file not found in {round_dir}")
        return False
    
    if plan_step_fp is None:
        print(f"Plan step JSON file not found in {round_dir}")
        return False
    
    # Load ground truth milestone for this scenario
    d_gt_milestone = next((item for item in gt_milestone_data if item.get("WW_id") == scenario_id), None)
    if d_gt_milestone is None:
        print(f"Ground truth milestone not found for scenario {scenario_id}")
        return False
    
    # Load steps and plan data
    try:
        with open(os.path.join(round_dir, step_json_fp), "r", encoding='utf-8') as f:
            steps = json.load(f)
        
        with open(os.path.join(round_dir, plan_step_fp), "r", encoding='utf-8') as f:
            plan_obj = json.load(f)
    except Exception as e:
        print(f"Error loading JSON files for scenario {scenario_id}, round {round_num}: {e}")
        return False
    
    if not steps:
        print(f"No steps found for scenario {scenario_id}, round {round_num}")
        return False
    
    print(f"Processing scenario {scenario_id}, round {round_num} with {len(steps)} steps")
    
    if dry_run:
        print(f"[DRY RUN] Would process scenario {scenario_id}, round {round_num}")
        return True
    
    # Check if output file already exists
    output_fp = os.path.join(round_dir, f"milestone_evaluation_scenario_{scenario_id}.json")
    if os.path.exists(output_fp):
        print(f"Output file already exists, skipping scenario {scenario_id}, round {round_num}: {output_fp}")
        return True
    
    # Process the scenario with all steps (no trial-based processing)
    try:
        # Prepare user data with all steps
        usr_data = {
            'question': d_gt_milestone['question'],
            'ground_truth_answer': d_gt_milestone['ground_truth_answer'],
            'milestones': d_gt_milestone['milestones'],
            'session_log': steps,
        }
        
        # Prepare messages for API call
        messages = [
            {"role": "system", "content": prompt_tmpl['system']},
            {"role": "user", "content": json.dumps(usr_data, ensure_ascii=False)}
        ]
        
        # Make API call
        response = _make_api_call(
            client, 
            model=model, 
            messages=messages, 
            max_tokens=1000, 
            response_format={"type": "json_object"}
        )
        
        if response is None:
            print(f"Skipping scenario {scenario_id}, round {round_num} due to API error.")
            return False
        
        # Parse response
        try:
            output_json = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"JSON decode error for scenario {scenario_id}, round {round_num}: {e}")
            output_json = {"error": "JSON decode error", "raw_response": response}
        
        # Add metadata
        output_json['scenario'] = scenario_id
        output_json['round'] = round_num
        output_json['total_steps'] = len(steps)
        
        # Save result
        with open(output_fp, "w", encoding='utf-8') as out_f:
            out_f.write(json.dumps(output_json, ensure_ascii=False, indent=2))
        
        time.sleep(1)  # Rate limiting
        
        print(f"Successfully processed scenario {scenario_id}, round {round_num}")
        return True
        
    except Exception as e:
        print(f"Error processing scenario {scenario_id}, round {round_num}: {e}")
        traceback.print_exc()
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Batch milestone evaluation for scenarios")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without API calls")
    parser.add_argument("--scenarios", type=str, help="JSON list of scenario IDs to process (e.g., '[3, 5, 9]'). If not provided, all scenarios in logs_dir will be processed.")
    parser.add_argument("--rounds", type=str, default='[5, 6, 7]', help="JSON list of rounds to process")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model to use for evaluation")
    parser.add_argument(
        "--azure-endpoint",
        type=str,
        default=DEFAULT_AZURE_OPENAI_ENDPOINT,
        help="Azure OpenAI endpoint (default from AZURE_OPENAI_ENDPOINT env var)",
    )
    
    args = parser.parse_args()
    
    if not args.azure_endpoint:
        parser.error(
            f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
        )

    
    # Parse scenarios and rounds
    target_scenarios = None
    if args.scenarios:
        try:
            target_scenarios = json.loads(args.scenarios)
        except json.JSONDecodeError:
            print(f"Invalid JSON format for scenarios: {args.scenarios}")
            return
    
    try:
        target_rounds = json.loads(args.rounds)
    except json.JSONDecodeError:
        print(f"Invalid JSON format for rounds: {args.rounds}")
        return
    
    # Set up paths
    base_dir = "/Data2/juezhang/ADA"
    logs_dir = os.path.join(base_dir, "logs_dki09")
    gt_milestone_fp = os.path.join(base_dir, "analysis/gt_milestone_extraction_results_gpt-5-chat-20250807.jsonl")
    prompt_tmpl_fp = os.path.join(base_dir, "analysis/prompt_lib/milestone_evaluator.yaml")
    
    # Load ground truth milestones and prompt template
    gt_milestone_data = load_gt_milestones(gt_milestone_fp)
    if not gt_milestone_data:
        print("Failed to load ground truth milestones")
        return
    
    prompt_tmpl = load_prompt_template(prompt_tmpl_fp)
    if prompt_tmpl is None:
        print("Failed to load prompt template")
        return
    
    # Initialize Azure OpenAI client (skip if dry run)
    client = None
    if not args.dry_run:
        try:
            api_version = "2024-08-01-preview"
            azure_endpoint = args.azure_endpoint or DEFAULT_AZURE_OPENAI_ENDPOINT
            if not azure_endpoint:
                print(
                    f"Azure endpoint not provided. Set {AZURE_OPENAI_ENDPOINT_ENV_VAR} or pass --azure-endpoint."
                )
                return

            client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
            )
            print("Successfully initialized Azure OpenAI client")
        except Exception as e:
            print(f"Failed to initialize Azure OpenAI client: {e}")
            return
    
    # Get scenario directories
    scenario_dirs = get_scenario_directories(logs_dir, target_scenarios)
    if not scenario_dirs:
        print("No scenario directories found")
        return
    
    if target_scenarios is None:
        print(f"No specific scenarios provided. Processing all {len(scenario_dirs)} scenarios found in {logs_dir}")
        scenario_ids = [scenario_id for scenario_id, _ in scenario_dirs]
        print(f"Scenarios to process: {sorted(scenario_ids)}")
    else:
        print(f"Processing {len(scenario_dirs)} specified scenarios: {sorted(target_scenarios)}")
    
    print(f"Target rounds: {target_rounds}")
    
    # Process each scenario-round combination
    total_combinations = len(scenario_dirs) * len(target_rounds)
    processed_count = 0
    success_count = 0
    
    with tqdm(total=total_combinations, desc="Processing scenario-round combinations") as pbar:
        for scenario_id, scenario_dir in scenario_dirs:
            for round_num in target_rounds:
                pbar.set_description(f"Processing scenario {scenario_id}, round {round_num}")
                
                success = process_scenario_round(
                    scenario_dir, scenario_id, round_num, 
                    gt_milestone_data, prompt_tmpl, client, args.model, args.dry_run
                )
                
                processed_count += 1
                if success:
                    success_count += 1
                
                pbar.update(1)
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {success_count}/{processed_count} scenario-round combinations")
    
    if args.dry_run:
        print("This was a dry run. No actual API calls were made.")

if __name__ == "__main__":
    main()
