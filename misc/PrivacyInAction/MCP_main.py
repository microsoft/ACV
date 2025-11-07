#!/usr/bin/env python3
"""
Complete script to process filtered_data.json:
1. Call add_fake_mail.py for Gmail items
2. Call add_fake_notion.py for NotionManager items
3. Call agent_flow.py with user instruction to execute the task
"""

import json
import subprocess
import sys
import os
import shlex
import time

def clear_results_directory(results_dir='data/results', logs_dir='data/logs'):
    """
    Clear all files in the specified results and logs directories.
    """
    # Clear results directory
    if os.path.exists(results_dir):
        for filename in os.listdir(results_dir):
            file_path = os.path.join(results_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                elif os.path.isdir(file_path):
                    # Recursively delete directory if needed
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"Deleted directory: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    else:
        print(f"Results directory {results_dir} does not exist. Creating it.")
        os.makedirs(results_dir)

    # Clear logs directory
    if os.path.exists(logs_dir):
        for filename in os.listdir(logs_dir):
            file_path = os.path.join(logs_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                elif os.path.isdir(file_path):
                    # Recursively delete directory if needed
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"Deleted directory: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    else:
        print(f"Logs directory {logs_dir} does not exist. Creating it.")
        os.makedirs(logs_dir)

def determine_scripts_to_run(item):
    """
    Determine which scripts to run based on the toolkits in the item
    Returns a list of scripts to run
    """
    toolkits = item.get('trajectory', {}).get('toolkits', [])
    scripts_to_run = []
    
    # Map toolkits to their corresponding scripts
    toolkit_script_map = {
        'Gmail': 'add_fake_mail.py',
        'NotionManager': 'add_fake_notion.py'
    }
    
    # Check each toolkit and add corresponding script
    for toolkit in toolkits:
        if toolkit in toolkit_script_map:
            scripts_to_run.append(toolkit_script_map[toolkit])
    
    return scripts_to_run

def run_script(script_name, *args):
    """
    Run a script with the given arguments and return the result
    """
    print(f"\nCalling {script_name} with args: {args}")
    
    cmd = [sys.executable, script_name] + list(map(str, args))
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Print output in real-time
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(f"  {output.strip()}")
    
    # Wait for the process to complete
    return_code = process.wait()
    
    return return_code

def process_filtered_data(json_file_path='data/filtered_data.json'):
    """
    Read filtered_data.json, extract user instructions, and run the complete flow for each item
    """
    # clear_results_directory()
    try:
        # Read the JSON file
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        
        total_items = len(data)
        print(f"Found {total_items} items to process")
        
        # Enumerate through the items
        for idx, item in enumerate(data, start=1):
            try:
                # Extract user instruction and toolkits
                user_instruction = item['trajectory']['user_instruction']
                toolkits = item.get('trajectory', {}).get('toolkits', [])
                
                print(f"\n{'='*60}")
                print(f"Processing Item {idx} of {total_items}")
                print(f"User Instruction: {user_instruction}")
                print(f"Toolkits: {', '.join(toolkits)}")
                print(f"{'='*60}")
                
                # Step 1 & 2: Add fake data (emails/events)
                scripts_to_run = determine_scripts_to_run(item)
                
                if not scripts_to_run:
                    print(f"Warning: No appropriate data scripts found for toolkits: {toolkits}")
                else:
                    # Run each data preparation script for this item
                    all_successful = True
                    for script in scripts_to_run:
                        return_code = run_script(script, idx)
                        
                        if return_code == 0:
                            print(f"\n✓ Successfully ran {script} for item {idx}")
                        else:
                            print(f"\n✗ Error running {script} for item {idx} (return code: {return_code})")
                            all_successful = False
                    
                    if not all_successful:
                        print(f"\n⚠ Skipping agent flow due to errors in data preparation")
                        continue
                
                # Step 3: Run the agent flow with user instruction
                print("\n" + "-"*40)
                print("Step 3: Running agent flow to complete the task")
                print("-"*40)

                
                
                # Pass the user instruction as a parameter
                # Using shlex.quote to properly escape the instruction for command line
                return_code = run_script('MCP_flow.py', idx, shlex.quote(user_instruction))
                
                if return_code == 0:
                    print(f"\n✓ Successfully completed agent flow for item {idx}")
                else:
                    print(f"\n✗ Error in agent flow for item {idx} (return code: {return_code})")
                
                print(f"{'='*60}")
                    
            except KeyError as e:
                print(f"Error: Missing key {e} in item {idx}")
            except Exception as e:
                print(f"Error processing item {idx}: {e}")
        
        print(f"\n\nAll items processed")
                
    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    process_filtered_data()