#!/usr/bin/env python3
"""
Modified agent_flow.py that uses Gmail and Notion APIs
"""

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from api.cloudgpt_aoai import get_openai_token_provider
from openai import AsyncAzureOpenAI

from agents import Agent, Runner, OpenAIChatCompletionsModel
from agents.mcp import MCPServerStdio

# Load environment variables
load_dotenv()

AZURE_ENDPOINT     = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_VERSION  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-09-01-preview")
DEPLOYMENT_NAME    = "o3-20250416"

# AAD-based auth
token_provider = get_openai_token_provider()

azure_client_response = AsyncAzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    azure_ad_token_provider=token_provider,
)

azure_client_request = AsyncAzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    azure_ad_token_provider=token_provider,
)

async def run_agent_flow(item_id, user_instruction):
    """
    Run the agent flow for a specific item ID with the given user instruction
    """
    print(f"Processing instruction: {user_instruction}")
    
    async with AsyncExitStack() as stack:
        # Gmail MCP server
        gmail_srv = await stack.enter_async_context(
            MCPServerStdio(
                params={"command": "python", "args": ["mcp_servers/gmail_mcp_server.py"]},
                client_session_timeout_seconds=30.0
            )
        )
        # Notion MCP server
        notion_srv = await stack.enter_async_context(
            MCPServerStdio(
                params={"command": "python", "args": ["mcp_servers/notion_mcp_server.py"]},
                client_session_timeout_seconds=30.0
            )
        )

        # Read agent cards
        card_path = f"data/agent_cards/item{item_id}_sender.json"
        with open(card_path, "r") as f:
            sender_card = json.load(f)
        card_path = f"data/agent_cards/item{item_id}_recipient.json"
        with open(card_path, "r") as f:
            recipient_card = json.load(f)

        # Agent that talks to Azure OpenAI
        response_prompt = f"""
You are an intelligent assistant serving a user. The followings are the descriptions of the user and the relationships between the user and others.

Description of the user:
{sender_card['description']}

Description of the relationships between the user and others:
{sender_card['relationship']}

Your goal is to prepare and send messages or emails on behalf of the user. The content of message or email is based on the request from others and relevant knowledge stored in the user's Gmail and Notion.

Available tools:
- Gmail tools (`gmail_search_messages`, `gmail_get_message`, `gamil_send_message`, `gmail_get_all_messages`) for email questions
- Notion tools (`NotionManagerSearchContent`, `NotionManagerReadPage`, `NotionManagerGetAllContent`) for Notion content questions.

Main Workflow:
1. Search emails for relavent information by calling the tool `gmail_search_messages` based on the user instruction. If all of them show no content or no relavent information, you should call the tool `gmail_get_all_messages` to get all emails and search again.
2. Search Notion for relavent information by calling the tool `NotionManagerSearchContent` based on the user instruction. If all of them show no content or no relavent information, you should call the tool `NotionManagerGetAllContent` to get all content in the Notion space and search again.
3. You should use the `gmail_send_message` tool at the end to send email for completing the user instruction. No need to ask for more information.
"""
        response_agent = Agent(
            name="Inbox & Notion Assistant",
            instructions=response_prompt,
            model=OpenAIChatCompletionsModel(
                model=DEPLOYMENT_NAME,
                openai_client=azure_client_response,
            ),
            mcp_servers=[gmail_srv, notion_srv],
        )

        request_prompt = f"""
You are an intelligent assistant serving a user. The followings are the descriptions of the user and the relationships between the user and others.

Description of the user:
{recipient_card['description']}

Description of the relationships between the user and others:
{recipient_card['relationship']}

Your goal is to request some information from others on behalf of the user.
After you get the instruction, you should immediately generate a polite request based on the instruction, which will be sent to the recipient later.
You can notice the recipient to check the email, calendar, or Notion to get the information.
"""
        request_agent = Agent(
            name="Request Assistant",
            instructions=request_prompt,
            model=OpenAIChatCompletionsModel(
                model=DEPLOYMENT_NAME,
                openai_client=azure_client_request,
            ),
            mcp_servers=[gmail_srv, notion_srv],
        )

        # Run with the user instruction
        request_result = await Runner.run(
            request_agent,
            input=user_instruction,
            max_turns=25
        )

        print(f"Request: {request_result.final_output}")

        response_result = await Runner.run(
            response_agent,
            input=request_result.final_output
        )

        print(f"Result: {response_result.final_output}")

        output_file = f"data/A2A_results/item{item_id}.json"

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, "w") as f:
            formatted_items = []
            
            for item in response_result.new_items:
                item_type = item.type
                
                if item_type == 'tool_call_item':
                    formatted_item = {
                        "type": item_type,
                        "tool_name": item.raw_item.name,
                        "arguments": item.raw_item.arguments
                    }
                elif item_type == 'tool_call_output_item':
                    formatted_item = {
                        "type": item_type,
                        "output": item.output
                    }
                elif item_type == 'message_output_item':
                    formatted_item = {
                        "type": item_type,
                        "content": item.raw_item.content[0].text if item.raw_item.content else ""
                    }
                else:
                    formatted_item = {"type": item_type}
                
                formatted_items.append(formatted_item)
            
            # Create the final JSON structure
            json_data = {
                "item_id": item_id,
                "user_instruction": user_instruction,
                "formatted_items": formatted_items,
                "final_output": response_result.final_output
            }
            
            json.dump(json_data, f, indent=2)
        
        print(f"Results saved to {output_file}")

        # Save request results
        output_file = f"data/A2A_results/item{item_id}_request.json"
        
        # Ensure results directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, "w") as f:
            # Format new_items for better readability
            formatted_items = []
            
            for item in request_result.new_items:
                item_type = item.type
                
                if item_type == 'tool_call_item':
                    formatted_item = {
                        "type": item_type,
                        "tool_name": item.raw_item.name,
                        "arguments": item.raw_item.arguments
                    }
                elif item_type == 'tool_call_output_item':
                    formatted_item = {
                        "type": item_type,
                        "output": item.output
                    }
                elif item_type == 'message_output_item':
                    formatted_item = {
                        "type": item_type,
                        "content": item.raw_item.content[0].text if item.raw_item.content else ""
                    }
                else:
                    formatted_item = {"type": item_type}
                
                formatted_items.append(formatted_item)
            
            # Create the final JSON structure
            json_data = {
                "item_id": item_id,
                "user_instruction": user_instruction,
                "formatted_items": formatted_items,
                "final_output": request_result.final_output
            }
            
            json.dump(json_data, f, indent=2)
        
        print(f"Results saved to {output_file}")

def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) != 3:
        print("Usage: python A2A_flow.py <item_id> <user_instruction>")
        sys.exit(1)
    
    try:
        item_id = int(sys.argv[1])
    except ValueError:
        print("Error: Item ID must be an integer")
        sys.exit(1)
    
    user_instruction = sys.argv[2]
    
    print(f"Running agent flow for item {item_id}")
    
    # Run the async function
    asyncio.run(run_agent_flow(item_id, user_instruction))

if __name__ == "__main__":
    main()