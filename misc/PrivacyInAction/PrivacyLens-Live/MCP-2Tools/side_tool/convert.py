# import the necessary function from the module
from api.cloudgpt_aoai import get_chat_completion, cloudgpt_available_models
import re
import json
import os
import uuid

def extract_emails_and_notion_pages_from_trajectory(trajectory_data):
    """
    Extract all email and Notion page data from the trajectory data,
    concatenating information from various actions for the same ID
    
    Args:
        trajectory_data (str): The executable trajectory containing the context and actions
        
    Returns:
        tuple: (dict of email data by id, dict of Notion page data by id)
    """
    emails_by_id = {}  # Using dict to ensure uniqueness by ID and concatenate data
    pages_by_id = {}  # Using dict to ensure uniqueness by ID and concatenate data
    
    # Step 1: Extract email information from all relevant actions
    
    # Find all GmailSearchEmails actions to get basic email metadata
    email_search_pattern = r"Action: GmailSearchEmails\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    email_search_matches = re.findall(email_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in email_search_matches:
        try:
            # Parse the observation JSON
            observation_data = json.loads(observation.strip())
            if "emails" in observation_data and isinstance(observation_data["emails"], list):
                for email in observation_data["emails"]:
                    if isinstance(email, dict) and "id" in email:
                        email_id = email["id"]
                        
                        # Create a new entry or concatenate with existing one
                        if email_id not in emails_by_id:
                            emails_by_id[email_id] = {}
                        
                        # Concatenate with email metadata
                        for key, value in email.items():
                            if key in emails_by_id[email_id]:
                                # If the field already exists and is different, concatenate
                                if value != emails_by_id[email_id][key]:
                                    if isinstance(value, str) and isinstance(emails_by_id[email_id][key], str):
                                        emails_by_id[email_id][key] = f"{emails_by_id[email_id][key]}\n{value}"
                            else:
                                # If the field doesn't exist, just add it
                                emails_by_id[email_id][key] = value
                    elif isinstance(email, str):
                        # If it's just an ID string
                        email_id = email
                        if email_id not in emails_by_id:
                            emails_by_id[email_id] = {"id": email_id}
        except json.JSONDecodeError:
            print(f"Failed to parse email search observation: {observation[:100]}...")
    
    # Find all GmailReadEmail actions to get full email content
    gmail_read_pattern = r"Action: GmailReadEmail\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    gmail_read_matches = re.findall(gmail_read_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in gmail_read_matches:
        try:
            # Parse the action input to get the email ID
            input_data = json.loads(action_input.strip())
            
            # Check for either "id" or "email_id" in the input
            email_id = input_data.get("id") or input_data.get("email_id")
            
            # Parse the observation to get the email details
            observation_data = json.loads(observation.strip())
            
            # If no ID from input, try to get from observation
            if not email_id:
                email_id = observation_data.get("id") or observation_data.get("email_id")
            
            if email_id:
                # Create a new entry or concatenate with existing one
                if email_id not in emails_by_id:
                    emails_by_id[email_id] = {"id": email_id}
                
                # Concatenate with full email content
                for key, value in observation_data.items():
                    if key in emails_by_id[email_id]:
                        # If the field already exists and is different, concatenate
                        if value != emails_by_id[email_id][key]:
                            if isinstance(value, str) and isinstance(emails_by_id[email_id][key], str):
                                emails_by_id[email_id][key] = f"{emails_by_id[email_id][key]}\n{value}"
                    else:
                        # If the field doesn't exist, just add it
                        emails_by_id[email_id][key] = value
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to process GmailReadEmail: {e}")
    
    # Step 2: Extract Notion page information from all relevant actions
    
    # Find all NotionManagerSearchContent actions to get basic page metadata
    notion_search_pattern = r"Action: NotionManagerSearchContent\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    notion_search_matches = re.findall(notion_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in notion_search_matches:
        try:
            # Parse the observation JSON
            observation_data = json.loads(observation.strip())
            if "results" in observation_data and isinstance(observation_data["results"], list):
                for page in observation_data["results"]:
                    if isinstance(page, dict) and "id" in page:
                        page_id = page["id"]
                        
                        # Create a new entry or concatenate with existing one
                        if page_id not in pages_by_id:
                            pages_by_id[page_id] = {}
                        
                        # Concatenate with page metadata
                        for key, value in page.items():
                            if key in pages_by_id[page_id]:
                                # If the field already exists and is different, concatenate
                                if value != pages_by_id[page_id][key]:
                                    if isinstance(value, str) and isinstance(pages_by_id[page_id][key], str):
                                        pages_by_id[page_id][key] = f"{pages_by_id[page_id][key]}\n{value}"
                            else:
                                # If the field doesn't exist, just add it
                                pages_by_id[page_id][key] = value
                    elif isinstance(page, str):
                        # If it's just an ID string
                        page_id = page
                        if page_id not in pages_by_id:
                            pages_by_id[page_id] = {"id": page_id}
        except json.JSONDecodeError:
            print(f"Failed to parse Notion search observation: {observation[:100]}...")
    
    # Find all NotionManagerReadPage actions to get full page content
    notion_read_pattern = r"Action: NotionManagerReadPage\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    notion_read_matches = re.findall(notion_read_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in notion_read_matches:
        try:
            # Parse the action input to get the page ID
            input_data = json.loads(action_input.strip())
            
            # Check for "page_id" in the input
            page_id = input_data.get("page_id")
            
            # Parse the observation to get the page details
            observation_data = json.loads(observation.strip())
            
            # If no ID from input, try to get from observation
            if not page_id:
                page_id = observation_data.get("id")
            
            if page_id:
                # Create a new entry or concatenate with existing one
                if page_id not in pages_by_id:
                    pages_by_id[page_id] = {"id": page_id}
                
                # Concatenate with full page content
                for key, value in observation_data.items():
                    if key in pages_by_id[page_id]:
                        # If the field already exists and is different, concatenate
                        if value != pages_by_id[page_id][key]:
                            if isinstance(value, str) and isinstance(pages_by_id[page_id][key], str):
                                pages_by_id[page_id][key] = f"{pages_by_id[page_id][key]}\n{value}"
                    else:
                        # If the field doesn't exist, just add it
                        pages_by_id[page_id][key] = value
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to process NotionManagerReadPage: {e}")
    
    # Step 3: Filter out emails that don't have enough information
    emails_with_content = {}
    for email_id, email_data in emails_by_id.items():
        # Only include emails that have a body or at least subject, from, and to fields
        if "body" in email_data or ("subject" in email_data and "from" in email_data and "to" in email_data):
            # Ensure ID is set in the data
            email_data["id"] = email_id
            emails_with_content[email_id] = email_data
    
    # Ensure all pages have their ID field set
    for page_id, page_data in pages_by_id.items():
        page_data["id"] = page_id
    
    return emails_with_content, pages_by_id

def generate_email_from_data(email_data):
    """
    Generate an email based on specific email data using the CloudGPT OpenAI integration
    
    Args:
        email_data (dict): Single email entry from the parsed data
        
    Returns:
        str: Generated email in .eml format
    """
    # Check if we already have a body from GmailReadEmail
    has_body = "body" in email_data and email_data["body"]
    
    # Construct a prompt for the LLM to generate an email
    prompt = f"""
Given the following email data:

{json.dumps(email_data, indent=2)}

Please create a complete email in .eml format with all appropriate headers (From, To, Subject, Date, Message-ID)
and the full email body that would represent this email.

IMPORTANT: You must preserve ALL exact information from the provided data, including:
- Exact email addresses (from, to, cc)
- Exact subject line exactly as provided
- Exact timestamp/date
- All numbers, dates, amounts, percentages, or other numeric values
- All names, locations, and proper nouns
- All product names, model numbers, or identifiers
- If a body is provided, use it exactly as is

{'Use the provided email body EXACTLY as the content of the email without any modifications.' if has_body else 'Create a realistic email body based on the subject and available metadata, but make sure to include any specific details mentioned.'}

The email should be realistic and follow standard email format conventions.
Ensure the headers match the metadata provided (from, to, subject, timestamp).

The email output should be wrapped in ```eml tags.
"""

    try:
        # Call the model with our prompt
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are an email generating assistant that preserves exact data and details when creating emails based on metadata."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the generated email from the response
        email_content = response.choices[0].message.content
        # Extract content between ```eml tags
        email_content = re.search(r"```eml(.*)```", email_content, re.DOTALL)
        if email_content:
            email_content = email_content.group(1)
            # Remove leading empty lines
            email_content = re.sub(r'^(\s*\n)*', '', email_content)
            return email_content
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for email generation: {e}")
        return None

def generate_notion_page_from_data(page_data):
    """
    Generate a Notion page based on specific page data using the CloudGPT OpenAI integration
    
    Args:
        page_data (dict): Single Notion page entry from the parsed data
        
    Returns:
        str: Generated Notion page content in markdown format
    """
    # Construct a prompt for the LLM to generate a Notion page without metadata
    prompt = f"""
Given the following Notion page data:

{json.dumps(page_data, indent=2)}

Please create a clean Notion page in markdown format that would represent this page.

IMPORTANT: 
- Preserve ALL exact content from the provided data
- Use the exact title as provided
- Include all content blocks in the exact order and format
- Convert all blocks to appropriate markdown format
- Do NOT include any metadata like page ID, URLs, created time, etc.
- Do NOT include any code blocks or tables with metadata
- Only include the actual content that should be visible on the page

The markdown should only include:
- Title as the main heading (# Title)
- All content blocks converted to clean markdown
- No metadata sections or technical information

The markdown output should be wrapped in ```markdown tags.
"""

    try:
        # Call the model with our prompt
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are a Notion page generating assistant that creates clean markdown pages without metadata."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the generated Notion page from the response
        page_content = response.choices[0].message.content
        # Extract content between ```markdown tags
        page_content = re.search(r"```markdown(.*)```", page_content, re.DOTALL)
        if page_content:
            page_content = page_content.group(1)
            # Remove leading empty lines
            page_content = re.sub(r'^(\s*\n)*', '', page_content)
            return page_content
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for Notion page generation: {e}")
        return None

def save_data_as_log(data, file_path, data_type="Data"):
    """
    Save structured data as a log file (renamed from save_data_as_markdown)
    
    Args:
        data (dict): The data to save
        file_path (str): Path to save the log file
        data_type (str): Type of data (Email or Notion Page)
    """
    with open(file_path, 'w') as f:
        f.write(f"# {data_type} Structure\n\n")
        f.write("```json\n")
        f.write(json.dumps(data, indent=2))
        f.write("\n```\n\n")
        
        # Write a more readable version with sections
        f.write(f"## {data_type} Fields\n\n")
        
        # Sort keys to make output more consistent
        for key in sorted(data.keys()):
            value = data[key]
            f.write(f"### {key}\n\n")
            
            # Format the value based on its type
            if isinstance(value, list):
                if len(value) > 0:
                    f.write("```\n")
                    for item in value:
                        if isinstance(item, dict):
                            f.write(f"- {json.dumps(item, indent=2)}\n")
                        else:
                            f.write(f"- {item}\n")
                    f.write("```\n\n")
                else:
                    f.write("*Empty list*\n\n")
            elif isinstance(value, dict):
                f.write("```json\n")
                f.write(json.dumps(value, indent=2))
                f.write("\n```\n\n")
            elif isinstance(value, str):
                # Check if it's a long string
                if len(value) > 100 or '\n' in value:
                    f.write("```\n")
                    f.write(value)
                    f.write("\n```\n\n")
                else:
                    f.write(f"`{value}`\n\n")
            else:
                f.write(f"`{value}`\n\n")

def process_records(input_file, output_dir="data/converted"):
    """
    Process all records in a JSON file and generate emails and Notion pages
    
    Args:
        input_file (str): Path to the JSON file containing records
        output_dir (str): Directory to save generated outputs
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the JSON data
    with open(input_file, 'r') as file:
        data = json.load(file)
    
    # Process each record
    for i, record in enumerate(data, 1):
        name = record.get('name', f'item{i}')
        print(f"Processing record: {name}")
        
        # Create a directory for this item (or clear it if it exists)
        item_dir = os.path.join(output_dir, f"item{i}")
        if os.path.exists(item_dir):
            # Clear out the directory
            print(f"Clearing existing directory: {item_dir}")
            # Remove all files but keep the directory
            for file_name in os.listdir(item_dir):
                file_path = os.path.join(item_dir, file_name)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        else:
            # Create the directory if it doesn't exist
            os.makedirs(item_dir, exist_ok=True)
        
        # Extract the executable trajectory
        trajectory = record.get('trajectory', {}).get('executable_trajectory', '')
        if not trajectory:
            print(f"Skipping record {name} - no executable trajectory found")
            continue
        
        # Check if toolkits contain Gmail or Notion
        toolkits = record.get('trajectory', {}).get('toolkits', [])

        print(f"Toolkits: {toolkits}")
        
        # Extract emails and Notion pages from the trajectory - consolidated by ID
        emails_by_id, pages_by_id = extract_emails_and_notion_pages_from_trajectory(trajectory)

        print(f"Emails by ID: {emails_by_id}")
        print(f"Pages by ID: {pages_by_id}")
        
        # No need to save summary files - proceeding directly to content generation
        
        # Process extracted emails
        if 'Gmail' in toolkits and emails_by_id:
            print(f"Found {len(emails_by_id)} unique emails with substantial content in record {name}")
            for j, (email_id, email_data) in enumerate(emails_by_id.items(), 1):
                print(f"  Generating email {j}/{len(emails_by_id)} (ID: {email_id})")
                
                # Save the email data structure to a log file
                email_data_path = os.path.join(item_dir, f"{email_id}_data.log")
                save_data_as_log(email_data, email_data_path, "Email")
                
                # Generate and save the email content
                email_content = generate_email_from_data(email_data)
                if email_content:
                    # Save using the email ID from the data
                    email_file = os.path.join(item_dir, f"{email_id}.eml")
                    with open(email_file, 'w') as f:
                        f.write(email_content)
                    print(f"  Email saved: {email_file}")
        
        # Process extracted Notion pages
        if 'NotionManager' in toolkits and pages_by_id:
            print(f"Found {len(pages_by_id)} unique Notion pages in record {name}")
            for j, (page_id, page_data) in enumerate(pages_by_id.items(), 1):
                print(f"  Generating Notion page {j}/{len(pages_by_id)} (ID: {page_id})")
                
                # Save the page data structure to a log file
                page_data_path = os.path.join(item_dir, f"{page_id}_data.log")
                save_data_as_log(page_data, page_data_path, "Notion Page")
                
                # Generate and save the Notion page content
                page_content = generate_notion_page_from_data(page_data)
                if page_content:
                    # Save using the page ID from the data
                    page_file = os.path.join(item_dir, f"{page_id}.md")
                    with open(page_file, 'w') as f:
                        f.write(page_content)
                    print(f"  Notion page saved: {page_file}")

def main():
    """
    Main function to run the script
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Process JSON records to generate emails and Notion pages')
    parser.add_argument('--input', default='data/filtered_data.json', help='Input JSON file path')
    parser.add_argument('--output', default='data/converted', help='Output directory path')
    
    args = parser.parse_args()
    
    print(f"Processing records from {args.input}...")
    process_records(args.input, args.output)
    print("Processing complete!")

if __name__ == "__main__":
    main()