import json
from ...api.cloudgpt_aoai import get_chat_completion
from ..module import Logger

logger = Logger(__file__, 'INFO')

def filter_experiences_via_component(jsonl_path, filter_key, filter_value, intent):
    """Filter experiences from a JSONL file based on a key-value pair. (Currently return first three successful experiences)"""
    filtered_experiences = []
    with open(jsonl_path, "r") as jsonl_file:
        for line in jsonl_file:
            experience = json.loads(line)
            if experience.get(filter_key) == filter_value:
                filtered_experiences.append(experience)

    filtered_experiences = [exp for exp in filtered_experiences if exp.get("result") == "success"]
    satisfied_experiences = []
    for experience in filtered_experiences:
        task_type = experience.get("task_type")
        task_description = experience.get("task_description")
        chat_message = [
            {"role": "system", "content": "Your task is to determine if the provided task type and task description are related to the user's intent. Respond with 'yes' or 'no'."},
            {"role": "system", "content": f"Related means that similar things to query,similar aims to operate or similar cause to analyze."},
            {"role": "user", "content": f"User's intent: {intent}"},
            {"role": "user", "content": f"Task Type: {task_type}"},
            {"role": "user", "content": f"Task Description: {task_description}"}
        ]
        engine = "gpt-4o-20240513"
        flag = True
        for _ in range(3):
            response = get_chat_completion(engine=engine, messages=chat_message).choices[0].message.content.strip()
            if response.lower().strip() != "yes":
                flag = False
                break
        if flag:
            satisfied_experiences.append(experience)   
            logger.info(f"A related experience has been found!")     
        if len(satisfied_experiences) >= 3:
            break

    return satisfied_experiences