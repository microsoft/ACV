#!/usr/bin/env python3
import json
import re
import os
import argparse
import uuid
from typing import Dict, List, Any, Tuple

def extract_email_content(item_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Extract the email content from a gmail_send_message tool call in an agent execution trajectory.
    Only extracts from gmail_send_message tool calls.
    
    Args:
        item_data: The data for a specific item
        
    Returns:
        Tuple[bool, Dict[str, Any]]: (success, email_metadata)
                                     If success is False, email_metadata will be empty.
    """
    formatted_items = item_data.get("formatted_items", [])
    
    # Look for a gmail_send_message tool call
    for item in formatted_items:
        if item.get("type") == "tool_call_item" and item.get("tool_name") == "gmail_send_message":
            try:
                arguments = json.loads(item.get("arguments", "{}"))
                email_content = arguments.get("body", "")
                
                # Collect all email metadata, ensuring proper defaults
                email_metadata = {
                    "to": arguments.get("to", []) or [],
                    "cc": arguments.get("cc", []) or [],
                    "bcc": arguments.get("bcc", []) or [],
                    "subject": arguments.get("subject", ""),
                    "body": email_content
                }
                
                # Make sure they are lists
                if not isinstance(email_metadata["to"], list):
                    email_metadata["to"] = [str(email_metadata["to"])]
                if not isinstance(email_metadata["cc"], list):
                    email_metadata["cc"] = [str(email_metadata["cc"])]
                if not isinstance(email_metadata["bcc"], list):
                    email_metadata["bcc"] = [str(email_metadata["bcc"])]
                
                return True, email_metadata
            except json.JSONDecodeError:
                print(f"Failed to parse gmail_send_message arguments")
    
    # No gmail_send_message tool call found
    return False, {}

def get_item_ids_in_results_dir(results_dir: str) -> List[int]:
    """
    Get all item IDs from the results directory by looking at JSON filenames.
    
    Args:
        results_dir: Directory containing results JSON files
        
    Returns:
        List[int]: List of item IDs found in the directory
    """
    item_ids = []
    
    # Check if directory exists
    if not os.path.isdir(results_dir):
        print(f"Results directory {results_dir} does not exist")
        return item_ids
    
    # Pattern to match item{id}.json files
    pattern = re.compile(r'item(\d+)\.json$')
    
    # Iterate through files in the directory
    for filename in os.listdir(results_dir):
        match = pattern.match(filename)
        if match:
            try:
                item_id = int(match.group(1))
                item_ids.append(item_id)
            except ValueError:
                continue
    
    return sorted(item_ids)

def extract_email_for_item(item_id: int, results_dir: str, output_dir: str) -> bool:
    """
    Extract email for a specific item (only from gmail_send_message) and save it as an EML file.
    
    Args:
        item_id: The ID of the item to extract email from
        results_dir: Directory containing results
        output_dir: Directory to save extracted emails
        
    Returns:
        bool: True if email was successfully extracted and saved, False otherwise
    """
    # Load the item data
    item_file_path = os.path.join(results_dir, f"item{item_id}.json")
    try:
        with open(item_file_path, 'r') as f:
            item_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading item data: {e}")
        return False
    
    # Extract the email content and metadata (only from gmail_send_message)
    success, email_metadata = extract_email_content(item_data)
    if not success:
        print(f"No gmail_send_message found in item {item_id}")
        return False
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save the extracted email to an EML file
    email_file_path = os.path.join(output_dir, f"email_item{item_id}.eml")
    
    # Extract email components
    email_to = ", ".join(email_metadata.get("to", []))
    email_cc = ", ".join(email_metadata.get("cc", []))
    email_bcc = ", ".join(email_metadata.get("bcc", []))
    email_subject = email_metadata.get("subject", "")
    email_text = email_metadata.get("body", "")
    
    # Generate a simple EML format
    eml_content = f"""To: {email_to}
"""
    
    if email_cc:
        eml_content += f"CC: {email_cc}\n"
    
    if email_bcc:
        eml_content += f"BCC: {email_bcc}\n"
    
    eml_content += f"""Subject: {email_subject}
Date: {str(uuid.uuid4())}
Message-ID: <{str(uuid.uuid4())}@example.com>
Content-Type: text/plain; charset="UTF-8"

{email_text}
"""
    
    # Write to the EML file
    with open(email_file_path, 'w') as f:
        f.write(eml_content)
    
    print(f"✅ Saved extracted email to {email_file_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Extract emails from agent execution trajectories (only from gmail_send_message)')
    parser.add_argument('--item_id', type=int, help='Specific item ID to extract email from (optional)')
    parser.add_argument('--results_dir', default='finalversionmiti4rebuttal/results', help='Directory containing results')
    parser.add_argument('--output_dir', default='finalversionmiti4rebuttal/extracted_emails', help='Directory to save extracted emails')
    parser.add_argument('--extract_all', action='store_true', help='Extract emails from all items in results directory')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Determine which items to process
    items_to_process = []
    if args.extract_all or not args.item_id:
        items_to_process = get_item_ids_in_results_dir(args.results_dir)
        if not items_to_process:
            print(f"No item files found in {args.results_dir}")
            return
        print(f"Found {len(items_to_process)} items to process: {items_to_process}")
    else:
        items_to_process = [args.item_id]
    
    # Process each item
    successful_extractions = 0
    skipped_items = []
    for item_id in items_to_process:
        print(f"\n=== PROCESSING ITEM {item_id} ===")
        if extract_email_for_item(item_id, args.results_dir, args.output_dir):
            successful_extractions += 1
        else:
            skipped_items.append(item_id)
    
    # Print overall summary
    print("\n=== EXTRACTION SUMMARY ===")
    print(f"Processed {len(items_to_process)} items")
    print(f"Successfully extracted {successful_extractions} emails")
    print(f"Skipped {len(skipped_items)} items (no gmail_send_message found)")
    if skipped_items:
        print("\nSkipped items:")
        for item_id in sorted(skipped_items):
            print(f"- item{item_id}.json")
    print(f"\nAll emails saved to: {args.output_dir}")

if __name__ == "__main__":
    main()