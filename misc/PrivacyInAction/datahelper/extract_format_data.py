# import the necessary function from the module
from api.cloudgpt_aoai import get_chat_completion, cloudgpt_available_models
import re
import json
import csv
import os
from datetime import datetime
from typing import Optional, List

def extract_all_communication_data_from_trajectory(trajectory_data):
    """
    Extract all email, Notion page, Messenger conversation, Slack message, and Calendar data
    from the trajectory data, concatenating information from various actions for the same ID
    
    Args:
        trajectory_data (str): The executable trajectory containing the context and actions
        
    Returns:
        tuple: (dict of email data by id, dict of Notion page data by id, 
                dict of Messenger conversation data by id, dict of Slack message data by id,
                list of Calendar event data)
    """
    emails_by_id = {}
    pages_by_id = {}
    messenger_convos_by_id = {}
    slack_messages_by_id = {}
    calendar_events = []
    
    # Step 1: Extract email information from all relevant actions
    email_search_pattern = r"Action: GmailSearchEmails\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    email_search_matches = re.findall(email_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in email_search_matches:
        try:
            # Clean up the observation data
            observation_clean = observation.strip()
            if not observation_clean.startswith('{'):
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
                    
            observation_data = json.loads(observation_clean)
            if "emails" in observation_data and isinstance(observation_data["emails"], list):
                for email in observation_data["emails"]:
                    if isinstance(email, dict) and "id" in email:
                        email_id = email["id"]
                        if email_id not in emails_by_id:
                            emails_by_id[email_id] = {}
                        
                        for key, value in email.items():
                            if key in emails_by_id[email_id]:
                                if value != emails_by_id[email_id][key]:
                                    if isinstance(value, str) and isinstance(emails_by_id[email_id][key], str):
                                        emails_by_id[email_id][key] = f"{emails_by_id[email_id][key]}\n{value}"
                            else:
                                emails_by_id[email_id][key] = value
                    elif isinstance(email, str):
                        email_id = email
                        if email_id not in emails_by_id:
                            emails_by_id[email_id] = {"id": email_id}
        except json.JSONDecodeError:
            print(f"Failed to parse email search observation: {observation[:100]}...")
    
    # Find all GmailReadEmail actions to get full email content
    gmail_read_pattern = r"Action: GmailReadEmail\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    gmail_read_matches = re.findall(gmail_read_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in gmail_read_matches:
        try:
            input_data = json.loads(action_input.strip())
            email_id = input_data.get("id") or input_data.get("email_id")
            
            # Clean up the observation data
            observation_clean = observation.strip()
            if not observation_clean.startswith('{'):
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
                    
            observation_data = json.loads(observation_clean)
            
            if not email_id:
                email_id = observation_data.get("id") or observation_data.get("email_id")
            
            if email_id:
                if email_id not in emails_by_id:
                    emails_by_id[email_id] = {"id": email_id}
                
                for key, value in observation_data.items():
                    if key in emails_by_id[email_id]:
                        if value != emails_by_id[email_id][key]:
                            if isinstance(value, str) and isinstance(emails_by_id[email_id][key], str):
                                emails_by_id[email_id][key] = f"{emails_by_id[email_id][key]}\n{value}"
                    else:
                        emails_by_id[email_id][key] = value
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to process GmailReadEmail: {e}")
    
    # Step 2: Extract Notion page information from all relevant actions
    notion_search_pattern = r"Action: NotionManagerSearchContent\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    notion_search_matches = re.findall(notion_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in notion_search_matches:
        try:
            # Clean up the observation data by removing any non-JSON prefix text
            observation_clean = observation.strip()
            # If the observation starts with explanatory text, try to find the JSON part
            if not observation_clean.startswith('{'):
                # Look for the first { which should be the start of JSON
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
            
            observation_data = json.loads(observation_clean)
            if "results" in observation_data and isinstance(observation_data["results"], list):
                for page in observation_data["results"]:
                    if isinstance(page, dict) and "id" in page:
                        page_id = page["id"]
                        if page_id not in pages_by_id:
                            pages_by_id[page_id] = {}
                        
                        for key, value in page.items():
                            if key in pages_by_id[page_id]:
                                if value != pages_by_id[page_id][key]:
                                    if isinstance(value, str) and isinstance(pages_by_id[page_id][key], str):
                                        pages_by_id[page_id][key] = f"{pages_by_id[page_id][key]}\n{value}"
                            else:
                                pages_by_id[page_id][key] = value
                    elif isinstance(page, str):
                        page_id = page
                        if page_id not in pages_by_id:
                            pages_by_id[page_id] = {"id": page_id}
        except json.JSONDecodeError as e:
            print(f"Failed to parse Notion search observation: {observation[:100]}... Error: {e}")
    
    # Find all NotionManagerReadPage actions to get full page content
    notion_read_pattern = r"Action: NotionManagerReadPage\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    notion_read_matches = re.findall(notion_read_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in notion_read_matches:
        try:
            input_data = json.loads(action_input.strip())
            page_id = input_data.get("page_id")
            
            # Clean up the observation data
            observation_clean = observation.strip()
            if not observation_clean.startswith('{'):
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
                    
            observation_data = json.loads(observation_clean)
            
            if not page_id:
                page_id = observation_data.get("id")
            
            if page_id:
                if page_id not in pages_by_id:
                    pages_by_id[page_id] = {"id": page_id}
                
                for key, value in observation_data.items():
                    if key in pages_by_id[page_id]:
                        if value != pages_by_id[page_id][key]:
                            if isinstance(value, str) and isinstance(pages_by_id[page_id][key], str):
                                pages_by_id[page_id][key] = f"{pages_by_id[page_id][key]}\n{value}"
                    else:
                        pages_by_id[page_id][key] = value
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to process NotionManagerReadPage: {e}")

    # Step 3: Extract Messenger conversation information
    messenger_pattern = r"Action: MessengerReceiveMessage\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    messenger_matches = re.findall(messenger_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in messenger_matches:
        try:
            observation_data = json.loads(observation.strip())
            
            if "messages" in observation_data and isinstance(observation_data["messages"], list):
                for message in observation_data["messages"]:
                    if isinstance(message, dict) and "sender_id" in message:
                        sender_id = message["sender_id"]
                        conversation_id = f"conversation_{sender_id}"
                        
                        if conversation_id not in messenger_convos_by_id:
                            messenger_convos_by_id[conversation_id] = {
                                "id": conversation_id,
                                "name": f"Conversation with {sender_id}",
                                "participants": [sender_id, "me"],
                                "messages": []
                            }
                        
                        messenger_convos_by_id[conversation_id]["messages"].append({
                            "id": message.get("message_id", f"msg_{len(messenger_convos_by_id[conversation_id]['messages'])}"),
                            "sender_name": sender_id,
                            "timestamp": message.get("time", ""),
                            "content": message.get("message", "")
                        })
        except json.JSONDecodeError:
            print(f"Failed to parse MessengerReceiveMessage observation: {observation[:100]}...")
    
    # Step 4: Extract Slack message information from all relevant actions
    slack_channels_pattern = r"Action: SlackListChannels\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    slack_channels_matches = re.findall(slack_channels_pattern, trajectory_data, re.DOTALL)
    
    slack_channels = {}
    
    for action_input, observation in slack_channels_matches:
        try:
            observation_data = json.loads(observation.strip())
            if "channels" in observation_data and isinstance(observation_data["channels"], list):
                for channel in observation_data["channels"]:
                    if isinstance(channel, dict) and "id" in channel:
                        channel_id = channel["id"]
                        slack_channels[channel_id] = channel
        except json.JSONDecodeError:
            print(f"Failed to parse Slack channels observation: {observation[:100]}...")
    
    # Find all SlackSearchMessages actions to get messages
    slack_search_pattern = r"Action: SlackSearchMessages\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    slack_search_matches = re.findall(slack_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in slack_search_matches:
        try:
            observation_data = json.loads(observation.strip())
            if "messages" in observation_data and isinstance(observation_data["messages"], list):
                for message in observation_data["messages"]:
                    if isinstance(message, dict) and "ts" in message:
                        message_id = message.get("client_msg_id", message["ts"])
                        
                        if message_id not in slack_messages_by_id:
                            slack_messages_by_id[message_id] = message
                            
                            if "channel" in message and message["channel"] in slack_channels:
                                slack_messages_by_id[message_id]["channel_info"] = slack_channels[message["channel"]]
                        else:
                            for key, value in message.items():
                                slack_messages_by_id[message_id][key] = value
        except json.JSONDecodeError:
            print(f"Failed to parse Slack search observation: {observation[:100]}...")
    
    # Find all SlackSearchMessage actions (singular) to get full message details
    slack_search_singular_pattern = r"Action: SlackSearchMessage\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    slack_search_singular_matches = re.findall(slack_search_singular_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in slack_search_singular_matches:
        try:
            observation_data = json.loads(observation.strip())
            
            if "messages" in observation_data and isinstance(observation_data["messages"], list):
                for message in observation_data["messages"]:
                    if isinstance(message, dict):
                        message_id = message.get("file_id", f"{message.get('timestamp', '')}-{message.get('from', '')}")
                        
                        if message_id:
                            slack_messages_by_id[message_id] = {
                                "id": message_id,
                                "text": message.get("content", ""),
                                "timestamp": message.get("timestamp", ""),
                                "user": message.get("from", ""),
                                "channel": message.get("in", ""),
                                "raw_data": message
                            }
        except json.JSONDecodeError:
            print(f"Failed to parse SlackSearchMessage observation: {observation[:100]}...")
    
    # Find all SlackReceiveMessage actions to get messages
    slack_receive_pattern = r"Action: SlackReceiveMessage\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    slack_receive_matches = re.findall(slack_receive_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in slack_receive_matches:
        try:
            observation_data = json.loads(observation.strip())
            if "messages" in observation_data and isinstance(observation_data["messages"], list):
                for message in observation_data["messages"]:
                    if isinstance(message, dict) and "message_id" in message:
                        message_id = message["message_id"]
                        
                        if message_id not in slack_messages_by_id:
                            slack_messages_by_id[message_id] = {
                                "id": message_id,
                                "text": message.get("message", ""),
                                "timestamp": message.get("time", ""),
                                "user": message.get("sender_id", ""),
                                "channel": "direct_message",  # SlackReceiveMessage typically gets DMs
                                "raw_data": message
                            }
                        else:
                            # Update existing message with additional info
                            for key, value in message.items():
                                if key == "message":
                                    slack_messages_by_id[message_id]["text"] = value
                                elif key == "time":
                                    slack_messages_by_id[message_id]["timestamp"] = value
                                elif key == "sender_id":
                                    slack_messages_by_id[message_id]["user"] = value
                                else:
                                    slack_messages_by_id[message_id][key] = value
        except json.JSONDecodeError:
            print(f"Failed to parse SlackReceiveMessage observation: {observation[:100]}...")
    
    # Find all SlackSearchInChat actions to get chat messages
    slack_search_in_chat_pattern = r"Action: SlackSearchInChat\nAction Input: (.*?)\nObservation: (.*?)(?=\n\nAction:|$)"
    slack_search_in_chat_matches = re.findall(slack_search_in_chat_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in slack_search_in_chat_matches:
        try:
            observation_data = json.loads(observation.strip())
            if "results" in observation_data and isinstance(observation_data["results"], list):
                for message in observation_data["results"]:
                    if isinstance(message, dict) and "message_id" in message:
                        message_id = message["message_id"]
                        
                        if message_id not in slack_messages_by_id:
                            slack_messages_by_id[message_id] = {
                                "id": message_id,
                                "text": message.get("message", ""),
                                "timestamp": "",  # SlackSearchInChat doesn't typically include timestamp in the provided data
                                "user": "unknown",  # Extract from chat_id in action_input if available
                                "channel": "direct_message",  # SlackSearchInChat is typically for direct chats
                                "raw_data": message
                            }
                            
                            # Try to extract chat_id from action input for better context
                            try:
                                input_data = json.loads(action_input.strip())
                                chat_id = input_data.get("chat_id", "")
                                if chat_id:
                                    slack_messages_by_id[message_id]["chat_id"] = chat_id
                                    slack_messages_by_id[message_id]["channel"] = f"chat_with_{chat_id}"
                            except (json.JSONDecodeError, KeyError):
                                pass
                        else:
                            # Update existing message with additional info
                            for key, value in message.items():
                                if key == "message":
                                    slack_messages_by_id[message_id]["text"] = value
                                else:
                                    slack_messages_by_id[message_id][key] = value
        except json.JSONDecodeError:
            print(f"Failed to parse SlackSearchInChat observation: {observation[:100]}...")
    
    # Step 5: Extract Google Calendar events
    # First, look for GoogleCalendarReadEvents which contains the actual event details
    calendar_read_pattern = r"Action: GoogleCalendarReadEvents\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    calendar_read_matches = re.findall(calendar_read_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in calendar_read_matches:
        try:
            # Clean up the observation data
            observation_clean = observation.strip()
            if not observation_clean.startswith('{'):
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
                    
            observation_data = json.loads(observation_clean)
            
            if "event_details" in observation_data and isinstance(observation_data["event_details"], list):
                for event in observation_data["event_details"]:
                    if isinstance(event, dict):
                        calendar_events.append(event)
                        
        except json.JSONDecodeError as e:
            print(f"Failed to parse GoogleCalendarReadEvents observation: {observation[:100]}... Error: {e}")
    
    # Also look for GoogleCalendarSearchEvents for any direct event data
    calendar_search_pattern = r"Action: GoogleCalendarSearchEvents\nAction Input: (.*?)\n(?:.*?\n)*?Observation:\s*(?:\n)*\s*(.*?)(?=\n\nAction:|$)"
    calendar_search_matches = re.findall(calendar_search_pattern, trajectory_data, re.DOTALL)
    
    for action_input, observation in calendar_search_matches:
        try:
            # Clean up the observation data
            observation_clean = observation.strip()
            if not observation_clean.startswith('{'):
                json_start = observation_clean.find('{')
                if json_start != -1:
                    observation_clean = observation_clean[json_start:]
                    
            observation_data = json.loads(observation_clean)
            
            if "events" in observation_data and isinstance(observation_data["events"], list):
                for event in observation_data["events"]:
                    if isinstance(event, dict):
                        calendar_events.append(event)
                        
        except json.JSONDecodeError as e:
            print(f"Failed to parse GoogleCalendarSearchEvents observation: {observation[:100]}... Error: {e}")
    
    # Filter out emails that don't have enough information
    emails_with_content = {}
    for email_id, email_data in emails_by_id.items():
        if "body" in email_data or ("subject" in email_data and "from" in email_data and "to" in email_data):
            email_data["id"] = email_id
            emails_with_content[email_id] = email_data
    
    # Ensure all pages have their ID field set
    for page_id, page_data in pages_by_id.items():
        page_data["id"] = page_id
    
    # Ensure all Messenger conversations have their ID field set
    for convo_id, convo_data in messenger_convos_by_id.items():
        convo_data["id"] = convo_id
    
    # Ensure all Slack messages have an ID field set
    for msg_id, msg_data in slack_messages_by_id.items():
        if "id" not in msg_data:
            msg_data["id"] = msg_id
    
    return emails_with_content, pages_by_id, messenger_convos_by_id, slack_messages_by_id, calendar_events

def generate_email_from_data(email_data):
    """
    Generate an email based on specific email data using the CloudGPT OpenAI integration
    
    Args:
        email_data (dict): Single email entry from the parsed data
        
    Returns:
        str: Generated email in .eml format
    """
    has_body = "body" in email_data and email_data["body"]
    
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
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are an email generating assistant that preserves exact data and details when creating emails based on metadata."},
                {"role": "user", "content": prompt}
            ]
        )
        
        email_content = response.choices[0].message.content
        email_content = re.search(r"```eml(.*)```", email_content, re.DOTALL)
        if email_content:
            email_content = email_content.group(1)
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
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are a Notion page generating assistant that creates clean markdown pages without metadata."},
                {"role": "user", "content": prompt}
            ]
        )
        
        page_content = response.choices[0].message.content
        page_content = re.search(r"```markdown(.*)```", page_content, re.DOTALL)
        if page_content:
            page_content = page_content.group(1)
            page_content = re.sub(r'^(\s*\n)*', '', page_content)
            return page_content
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for Notion page generation: {e}")
        return None

def generate_messenger_conversation_from_data(convo_data):
    """
    Generate a simplified messenger conversation from data using CloudGPT OpenAI integration
    
    Args:
        convo_data (dict): Single Messenger conversation entry from the parsed data
        
    Returns:
        str: Generated Messenger conversation in simplified JSON format with text and user_name fields
    """
    prompt = f"""
Given the following Messenger conversation data:

{json.dumps(convo_data, indent=2)}

Please create a simplified JSON representation of this Messenger conversation.
The output should be an array of message objects, each containing:
- "text": The content of the message
- "user_name": The name or identifier of the user who sent the message

IMPORTANT:
- Preserve the exact order of messages
- Maintain the exact content of each message
- Use the exact sender names
- Do not add any interpretations or modifications to the message text
- Include all messages that have content
- The output should ONLY include an array of messages with text and user_name fields

The output should be a valid JSON array wrapped in ```json tags.
"""

    try:
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are a messaging data extraction assistant that creates simplified JSON representations of conversations."},
                {"role": "user", "content": prompt}
            ]
        )
        
        json_content = response.choices[0].message.content
        json_content = re.search(r"```json(.*)```", json_content, re.DOTALL)
        if json_content:
            json_content = json_content.group(1)
            json_content = re.sub(r'^(\s*\n)*', '', json_content)
            return json_content
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for Messenger conversation generation: {e}")
        return None

def generate_slack_messages_from_data(message_data):
    """
    Generate a simplified Slack message thread from data using CloudGPT OpenAI integration
    
    Args:
        message_data (dict): Single Slack message entry from the parsed data
        
    Returns:
        str: Generated Slack message in simplified JSON format with text and user_name fields
    """
    prompt = f"""
Given the following Slack message data:

{json.dumps(message_data, indent=2)}

Please create a simplified JSON representation of this Slack message and any replies.
The output should be an array of message objects, each containing:
- "text": The content of the message
- "user_name": The name or identifier of the user who sent the message

If there's only one message with no replies, the array should contain one object.
If there are replies, they should be included in the array after the main message.

IMPORTANT:
- Preserve the exact order of messages (main message first, followed by replies in order)
- Maintain the exact content of each message
- Use the exact user identifiers as provided
- Do not add any interpretations or modifications to the message text
- The output should ONLY include an array of messages with text and user_name fields

The output should be a valid JSON array wrapped in ```json tags.
"""

    try:
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are a Slack data extraction assistant that creates simplified JSON representations of messages."},
                {"role": "user", "content": prompt}
            ]
        )
        
        json_content = response.choices[0].message.content
        json_content = re.search(r"```json(.*)```", json_content, re.DOTALL)
        if json_content:
            json_content = json_content.group(1)
            json_content = re.sub(r'^(\s*\n)*', '', json_content)
            return json_content
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for Slack message generation: {e}")
        return None

def generate_outlook_event_from_data(event_data):
    """
    Generate Outlook-formatted event data using LLM
    
    Args:
        event_data (dict): Single calendar event entry from the parsed data
        
    Returns:
        dict: Generated event in Outlook format or None if generation fails
    """
    prompt = f"""
Given the following Google Calendar event data:

{json.dumps(event_data, indent=2)}

Please extract and format this event data to match the Outlook event creation format.
The output should be a JSON object with the following fields:

- "subject": The event title/summary (required string)
- "start_time": Start date/time in ISO format (required string)
- "end_time": End date/time in ISO format (required string)  
- "location": Event location (optional string, null if not provided)
- "body": Event description/body content (optional string, null if not provided)
- "attendees": List of attendee email addresses (optional list of strings, null if not provided)
- "is_all_day": Whether this is an all-day event (boolean, default false)
- "importance": Event importance level (string: "low", "normal", or "high", default "normal")
- "reminder_minutes": Minutes before event to remind (optional integer, default 15)

IMPORTANT EXTRACTION RULES:
- Preserve ALL exact information from the provided data
- Use exact subject/summary as provided
- Convert start/end times to proper ISO format (YYYY-MM-DDTHH:MM:SS format)
- Extract attendee email addresses from the attendees array
- If no specific time is provided (date only), treat as all-day event
- Use the description field for the body content
- Set appropriate importance based on event content (meeting = normal, urgent = high, etc.)
- Default reminder to 15 minutes unless specified otherwise

The output should be a valid JSON object wrapped in ```json tags.
"""

    try:
        response = get_chat_completion(
            model="gpt-4o-20241120",
            messages=[
                {"role": "developer", "content": "You are a calendar event extraction assistant that converts Google Calendar events to Outlook format while preserving exact data."},
                {"role": "user", "content": prompt}
            ]
        )
        
        event_content = response.choices[0].message.content
        json_match = re.search(r"```json(.*)```", event_content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
            json_content = re.sub(r'^(\s*\n)*', '', json_content)
            
            try:
                outlook_event = json.loads(json_content)
                
                # Validate required fields
                required_fields = ["subject", "start_time", "end_time"]
                for field in required_fields:
                    if field not in outlook_event:
                        print(f"Warning: Missing required field '{field}' in generated event")
                        return None
                
                # Ensure proper data types
                if "is_all_day" not in outlook_event:
                    outlook_event["is_all_day"] = False
                if "importance" not in outlook_event:
                    outlook_event["importance"] = "normal"
                if "reminder_minutes" not in outlook_event:
                    outlook_event["reminder_minutes"] = 15
                
                return outlook_event
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse generated JSON: {e}")
                return None
        
        return None
    
    except Exception as e:
        print(f"Error calling the LLM for calendar event generation: {e}")
        return None

def save_data_as_log(data, file_path, data_type="Data"):
    """
    Save structured data as a log file
    
    Args:
        data (dict): The data to save
        file_path (str): Path to save the log file
        data_type (str): Type of data
    """
    with open(file_path, 'w') as f:
        f.write(f"# {data_type} Structure\n\n")
        f.write("```json\n")
        f.write(json.dumps(data, indent=2))
        f.write("\n```\n\n")
        
        # Write a more readable version with sections
        f.write(f"## {data_type} Fields\n\n")
        
        for key in sorted(data.keys()):
            value = data[key]
            f.write(f"### {key}\n\n")
            
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
                if len(value) > 100 or '\n' in value:
                    f.write("```\n")
                    f.write(value)
                    f.write("\n```\n\n")
                else:
                    f.write(f"`{value}`\n\n")
            else:
                f.write(f"`{value}`\n\n")

def save_outlook_events_to_csv(events_data, output_file):
    """
    Save Outlook-formatted events to CSV file
    
    Args:
        events_data (list): List of Outlook-formatted event dictionaries
        output_file (str): Path to the output CSV file
    """
    if not events_data:
        return
    
    headers = [
        "subject", "start_time", "end_time", "location", "body",
        "attendees", "is_all_day", "importance", "reminder_minutes", "original_id"
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for event in events_data:
            # Handle attendees list - convert to semicolon-separated string
            if "attendees" in event and isinstance(event["attendees"], list):
                event["attendees"] = "; ".join(event["attendees"])
            elif "attendees" not in event or event["attendees"] is None:
                event["attendees"] = ""
            
            writer.writerow(event)
    
    print(f"Calendar: {len(events_data)} Outlook events saved to {output_file}")

def process_records(input_file, output_dir="data/converted"):
    """
    Process all records in a JSON file and generate emails, Notion pages,
    Messenger conversations, Slack messages, and Calendar events
    
    Args:
        input_file (str): Path to the JSON file containing records
        output_dir (str): Directory to save generated outputs
    """
    os.makedirs(output_dir, exist_ok=True)
    
    with open(input_file, 'r') as file:
        data = json.load(file)
    
    # Process each record
    for i, record in enumerate(data, 1):
        name = record.get('name', f'item{i}')
        print(f"Processing record: {name}")
        
        # Create a directory for this item
        item_dir = os.path.join(output_dir, f"item{i}")
        if os.path.exists(item_dir):
            print(f"Clearing existing directory: {item_dir}")
            for file_name in os.listdir(item_dir):
                file_path = os.path.join(item_dir, file_name)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        else:
            os.makedirs(item_dir, exist_ok=True)
        
        trajectory = record.get('trajectory', {}).get('executable_trajectory', '')
        if not trajectory:
            print(f"Skipping record {name} - no executable trajectory found")
            continue
        
        toolkits = record.get('trajectory', {}).get('toolkits', [])
        print(f"Toolkits: {toolkits}")
        # Extract all data from the trajectory
        emails_by_id, pages_by_id, messenger_convos_by_id, slack_messages_by_id, calendar_events = extract_all_communication_data_from_trajectory(trajectory)
        print(f"Emails found: {len(emails_by_id)}")
        print(f"Notion pages found: {len(pages_by_id)}")
        print(f"Messenger conversations found: {len(messenger_convos_by_id)}")
        print(f"Slack messages found: {len(slack_messages_by_id)}")
        print(f"Calendar events found: {len(calendar_events)}")
        
        # Process extracted emails (.eml files)
        if any('Gmail' in toolkit for toolkit in toolkits) and emails_by_id:
            print(f"Found {len(emails_by_id)} unique emails with substantial content in record {name}")
            for j, (email_id, email_data) in enumerate(emails_by_id.items(), 1):
                print(f"  Generating email {j}/{len(emails_by_id)} (ID: {email_id})")
                
                # Save the email data structure to a log file
                email_data_path = os.path.join(item_dir, f"{email_id}_data.log")
                save_data_as_log(email_data, email_data_path, "Email")
                
                # Generate and save the email content
                email_content = generate_email_from_data(email_data)
                if email_content:
                    email_file = os.path.join(item_dir, f"{email_id}.eml")
                    with open(email_file, 'w') as f:
                        f.write(email_content)
                    print(f"  Email saved: {email_file}")
        
        # Process extracted Notion pages (.md files)
        if any('NotionManager' in toolkit for toolkit in toolkits) and pages_by_id:
            print(f"Found {len(pages_by_id)} unique Notion pages in record {name}")
            for j, (page_id, page_data) in enumerate(pages_by_id.items(), 1):
                print(f"  Generating Notion page {j}/{len(pages_by_id)} (ID: {page_id})")
                
                # Save the page data structure to a log file
                page_data_path = os.path.join(item_dir, f"{page_id}_data.log")
                save_data_as_log(page_data, page_data_path, "Notion Page")
                
                # Generate and save the Notion page content
                page_content = generate_notion_page_from_data(page_data)
                if page_content:
                    page_file = os.path.join(item_dir, f"{page_id}.md")
                    with open(page_file, 'w') as f:
                        f.write(page_content)
                    print(f"  Notion page saved: {page_file}")
        
        # Process extracted Messenger conversations (.json files)
        if any('Messenger' in toolkit for toolkit in toolkits) and messenger_convos_by_id:
            print(f"Found {len(messenger_convos_by_id)} unique Messenger conversations in record {name}")
            for j, (convo_id, convo_data) in enumerate(messenger_convos_by_id.items(), 1):
                print(f"  Generating Messenger conversation {j}/{len(messenger_convos_by_id)} (ID: {convo_id})")
                
                # Save the conversation data structure to a log file
                convo_data_path = os.path.join(item_dir, f"messenger_{convo_id}_data.log")
                save_data_as_log(convo_data, convo_data_path, "Messenger Conversation")
                
                # Generate and save the conversation content as JSON
                convo_content = generate_messenger_conversation_from_data(convo_data)
                if convo_content:
                    convo_file = os.path.join(item_dir, f"messenger_{convo_id}.json")
                    with open(convo_file, 'w') as f:
                        f.write(convo_content)
                    print(f"  Messenger conversation saved: {convo_file}")
        
        # Process extracted Slack messages (.json files)
        if any('Slack' in toolkit for toolkit in toolkits) and slack_messages_by_id:
            print(f"Found {len(slack_messages_by_id)} unique Slack messages in record {name}")
            for j, (msg_id, msg_data) in enumerate(slack_messages_by_id.items(), 1):
                print(f"  Generating Slack message {j}/{len(slack_messages_by_id)} (ID: {msg_id})")
                
                # Save the message data structure to a log file
                msg_data_path = os.path.join(item_dir, f"slack_{msg_id}_data.log")
                save_data_as_log(msg_data, msg_data_path, "Slack Message")
                
                # Generate and save the message content as JSON
                msg_content = generate_slack_messages_from_data(msg_data)
                if msg_content:
                    safe_msg_id = re.sub(r'[^\w.-]', '_', msg_id)
                    msg_file = os.path.join(item_dir, f"slack_{safe_msg_id}.json")
                    with open(msg_file, 'w') as f:
                        f.write(msg_content)
                    print(f"  Slack message saved: {msg_file}")
        
        # Process extracted Calendar events (.csv file with Outlook format)
        if any('GoogleCalendar' in toolkit for toolkit in toolkits) and calendar_events:
            print(f"Found {len(calendar_events)} calendar events in record {name}")
            outlook_events = []
            
            for j, raw_event in enumerate(calendar_events, 1):
                print(f"  Processing calendar event {j}/{len(calendar_events)}: {raw_event.get('summary', 'Untitled')}")
                
                # Generate Outlook-formatted event using LLM
                outlook_event = generate_outlook_event_from_data(raw_event)
                if outlook_event:
                    # Add metadata
                    outlook_event['original_id'] = raw_event.get('id', '')
                    outlook_events.append(outlook_event)
                    print(f"    ✓ Generated Outlook event: {outlook_event['subject']}")
                else:
                    print(f"    ✗ Failed to generate Outlook event")
            
            if outlook_events:
                # Save calendar events as CSV
                calendar_csv_file = os.path.join(item_dir, f"calendar_events.csv")
                save_outlook_events_to_csv(outlook_events, calendar_csv_file)
                
                # Also save as JSON for reference
                calendar_json_file = os.path.join(item_dir, f"calendar_events.json")
                with open(calendar_json_file, 'w', encoding='utf-8') as jsonfile:
                    json.dump(outlook_events, jsonfile, indent=2, ensure_ascii=False)
                print(f"  Calendar events also saved as JSON: {calendar_json_file}")

def main():
    """
    Main function to run the script
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Process JSON records to generate all communication data with proper formats')
    parser.add_argument('--input', default='newgenerateddata/final_data.json', help='Input JSON file path')
    parser.add_argument('--output', default='newgenerateddata/converted', help='Output directory path')
    
    args = parser.parse_args()
    
    print(f"Processing records from {args.input}...")
    print("Output formats:")
    print("  📧 Gmail      -> .eml files")
    print("  📝 Notion     -> .md files")
    print("  💬 Messenger  -> .json files")
    print("  💼 Slack      -> .json files")
    print("  📅 Calendar   -> .csv files (Outlook format)")
    print()
    
    process_records(args.input, args.output)
    print("Processing complete!")

if __name__ == "__main__":
    main() 