import yaml
from ..api.cloudgpt_aoai import get_chat_completion
import json

def load_prompt_from_yaml(yaml_path, markdown_content):
    """Load system and user messages from a YAML file and replace placeholders."""
    with open(yaml_path, "r") as file:
        prompt_data = yaml.safe_load(file)

    system_message = prompt_data["system_message"]
    user_message = prompt_data["user_message"].replace("{markdown_content}", markdown_content)

    return system_message, user_message

import os

def add_experience(namespace, markdown_text, yaml_path="prompts/generate_mem.yaml"):
    yaml_path = os.path.join(os.path.dirname(__file__), yaml_path)
    # Load system and user messages
    system_message, user_message = load_prompt_from_yaml(yaml_path, markdown_text)

    chat_message = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": "Now, given the following chat log:"},
        {"role": "user", "content": user_message}
    ]
    engine = "gpt-4-turbo-20240409"

    response = get_chat_completion(engine=engine, messages=chat_message)
    # Extract and format the response
    json_output = response.choices[0].message.content.strip()

    json_output = json_output[json_output.find("{"):json_output.rfind("}")+1]
    parsed_json = json.loads(json_output)

    # Save to a JSONL file
    with open(f"src/self_exploration/experience_bank/{namespace}.jsonl", "a") as jsonl_file:
        jsonl_file.write(json.dumps(parsed_json) + "\n")
    
    print("Memories added successfully!")