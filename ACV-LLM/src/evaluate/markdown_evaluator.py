import os
import yaml
import time
import re
from typing import Dict, Any
from ..global_utils.cloudgpt_aoai import get_chat_completion
from ..global_utils.chat_with_o1 import get_o1_chat_completion

def load_prompts_from_yaml(file_path: str) -> Dict[str, Any]:
    """Loads all prompts from a specified YAML file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"YAML file not found at {file_path}")
    with open(file_path, 'r', encoding='utf-8') as yaml_file:
        return yaml.safe_load(yaml_file)


def _load_markdown2chat_message(markdown_file_path: str, prompt_key: str) -> dict:
    """Converts markdown content to a structured chat message based on 
    a template from a YAML file.
    """
    prompts = load_prompts_from_yaml("prompts/eval-v2.yaml")
    if prompt_key not in prompts:
        raise KeyError(f"Prompt key '{prompt_key}' not found in the YAML file.")
    if not os.path.exists(markdown_file_path):
        raise FileNotFoundError(f"File not found: {markdown_file_path}")

    with open(markdown_file_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()

    prompt_data = prompts[prompt_key]
    task_description = prompt_data.get('description', '').format(markdown_content=markdown_content)
    # print(task_description)
    issue_description = f"The issue is about {markdown_file_path}"
    # print(issue_description)
    return [
        {"role": "user", "content": task_description},
        {"role": "user", "content": issue_description}
    ]

def _call_llm4response(chat_message, engine):
    if engine == "dev-gpt-o1-preview":
        return get_o1_chat_completion(engine=engine, messages=chat_message)
    else:
        return get_chat_completion(engine=engine, messages=chat_message)

def _call_llm4judge(chat_message, hash_code, file_name):
    """Evaluates a structured chat message using a language model to determine a True/False outcome.

    Args:
        chat_message (dict): The chat message to evaluate.

    Returns:
        bool: True if the model's response contains "TRUE", False if it contains "FALSE".

    Raises:
        ValueError: If the model does not return a clear TRUE or FALSE response.
    """
    # engine = "dev-gpt-o1-preview"
    engine = "gpt-4-turbo-20240409"
    # print(chat_message)
    response = _call_llm4response(chat_message, engine=engine)
    # print(response)

    response_content = response.choices[0].message.content.strip()

    # print(response_content)
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
    """Calculates the number of steps for each round in a markdown file.

    Args:
        markdown_file_path (str): The path to the markdown file.

    Returns:
        Dict[str, int]: A dictionary mapping each round to the number of steps it contains.

    Raises:
        FileNotFoundError: If the markdown file does not exist at the specified path.
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
