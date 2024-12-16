# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import yaml
import re
from typing import Dict, Any
from ..global_utils.cloudgpt_aoai import get_chat_completion

def load_prompts_from_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load all prompts from a specified YAML file.

    Parameters:
    - file_path (str): The path to the YAML file.

    Returns:
    - Dict[str, Any]: A dictionary containing the prompts.

    Raises:
    - FileNotFoundError: If the specified YAML file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"YAML file not found at {file_path}")
    with open(file_path, 'r', encoding='utf-8') as yaml_file:
        return yaml.safe_load(yaml_file)

def _load_markdown2chat_message(markdown_file_path: str, prompt_key: str) -> dict:
    """
    Convert markdown content to a structured chat message based on a YAML prompt template.

    Parameters:
    - markdown_file_path (str): The path to the markdown file.
    - prompt_key (str): The key to retrieve the relevant prompt from the YAML file.

    Returns:
    - list[dict]: A list of chat message dictionaries.

    Raises:
    - KeyError: If the prompt key is not found in the YAML file.
    - FileNotFoundError: If the markdown file does not exist.
    """
    prompts = load_prompts_from_yaml("prompts/eval.yaml")
    if prompt_key not in prompts:
        raise KeyError(f"Prompt key '{prompt_key}' not found in the YAML file.")
    if not os.path.exists(markdown_file_path):
        raise FileNotFoundError(f"File not found: {markdown_file_path}")

    with open(markdown_file_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()

    prompt_data = prompts[prompt_key]
    task_description = prompt_data.get('description', '').format(markdown_content=markdown_content)
    issue_description = f"The issue is about {markdown_file_path}"
    return [
        {"role": "user", "content": task_description},
        {"role": "user", "content": issue_description}
    ]

def _call_llm4response(chat_message, engine):
    """
    Call a language model to generate a response based on the provided chat message.

    Parameters:
    - chat_message (list[dict]): The structured chat message to send to the model.
    - engine (str): The LLM engine to use.

    Returns:
    - Response object from the language model.
    """
    return get_chat_completion(engine=engine, messages=chat_message)

def _call_llm4judge(chat_message, hash_code, file_name):
    """
    Evaluate a structured chat message using a language model and determine True/False.

    Parameters:
    - chat_message (list[dict]): The chat message to evaluate.
    - hash_code (str): A unique hash code to identify the session or task.
    - file_name (str): The file name to save the response content.

    Returns:
    - bool: True if the response contains "TRUE", False if it contains "FALSE".

    Raises:
    - ValueError: If the response does not clearly contain "TRUE" or "FALSE".
    """
    engine = "gpt-4-turbo-20240409"
    response = _call_llm4response(chat_message, engine=engine)
    response_content = response.choices[0].message.content.strip()

    folder_path = f"results/chat_history/{hash_code}"
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, f"{file_name}.md")
    with open(file_path, "w") as file:
        file.write(f"{response_content}")

    if re.search(r'\$TRUE\$', response_content, re.IGNORECASE):
        return True
    elif re.search(r'\$FALSE\$', response_content, re.IGNORECASE):
        return False
    else:
        raise ValueError("The model did not return a clear TRUE or FALSE response.")

def _calculate_steps(markdown_file_path: str) -> Dict[str, int]:
    """
    Calculate the number of steps for each round in a markdown file.

    Parameters:
    - markdown_file_path (str): The path to the markdown file.

    Returns:
    - Dict[str, int]: A dictionary mapping each round to its step count.

    Raises:
    - FileNotFoundError: If the markdown file does not exist.
    """
    if not os.path.exists(markdown_file_path):
        raise FileNotFoundError(f"File not found: {markdown_file_path}")

    with open(markdown_file_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()

    step_pattern = re.compile(r'==================== Step (\d+) ====================')
    step_counts = {}
    current_round = 0

    for line in markdown_content.splitlines():
        if line.startswith("Solving task"):
            current_round += 1
            step_counts[current_round] = 0

        if step_pattern.match(line) and current_round:
            step_counts[current_round] += 1

    return step_counts
