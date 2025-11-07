#!/usr/bin/env python3

import json
import os
import re
from pathlib import Path

def filter_and_renumber_data(data):
    """
    Filter data to keep only items with specific toolkits,
    then renumber them sequentially as main1, main2, etc.
    
    Args:
        data (list): List of items with trajectory and toolkits
        
    Returns:
        list: Filtered list of items with sequentially renumbered names
    """
    specific_toolkits = ["Gmail", "Messenger", "NotionManager", "Slack", "GoogleCalendar"]
    filtered_data = []
    
    # First filter the data
    for item in data:
        if "trajectory" in item and "toolkits" in item["trajectory"]:
            toolkits = item["trajectory"]["toolkits"]
            
            # Check if ALL toolkits in the datapoint are from our specific list
            all_toolkits_are_valid = True
            for toolkit in toolkits:
                # Check if this toolkit is in our allowed list
                toolkit_is_valid = False
                for specific in specific_toolkits:
                    if specific in toolkit:
                        toolkit_is_valid = True
                        break
                
                # If this toolkit isn't valid, the entire datapoint is invalid
                if not toolkit_is_valid:
                    all_toolkits_are_valid = False
                    break
            
            # Keep only datapoints where ALL toolkits are valid
            if all_toolkits_are_valid:
                filtered_data.append(item)
    
    # Now renumber the filtered items sequentially
    for idx, item in enumerate(filtered_data, 1):
        if "name" in item:
            # Keep the "main" prefix but update the number
            item["name"] = f"main{idx}"
    
    return filtered_data

def main():
    """
    Main function to read input file, filter data, renumber items, and write output file
    """
    input_file = "newgenerateddata/main_data.json"
    output_file = "newgenerateddata/final_data.json"
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    try:
        # Read the input file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"Successfully loaded data from {input_file} ({len(data)} items)")
        
        # Print original names (for comparison)
        original_names = [item.get('name', 'unnamed') for item in data]
        print(f"Original names: {', '.join(original_names)}")
        
        # Filter and renumber the data
        processed_data = filter_and_renumber_data(data)
        
        print(f"Processed data: kept {len(processed_data)} items after filtering")
        print(f"Dropped {len(data) - len(processed_data)} items that contained other toolkits")
        
        # Print the renumbered names
        new_names = [item.get('name', 'unnamed') for item in processed_data]
        print(f"Renumbered names: {', '.join(new_names)}")
        
        # Show the mapping from old to new names
        print("\nName changes:")
        original_kept_names = []
        for i, item in enumerate(data):
            if any(proc_item.get('id', None) == item.get('id', None) for proc_item in processed_data):
                original_kept_names.append(item.get('name', 'unnamed'))
        
        for old_name, new_name in zip(original_kept_names, new_names):
            print(f"- {old_name} → {new_name}")
        
        # Write the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=4)
        
        print(f"\nSuccessfully saved processed data to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: Could not find the input file at {input_file}")
    except json.JSONDecodeError:
        print(f"Error: The file {input_file} does not contain valid JSON")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()