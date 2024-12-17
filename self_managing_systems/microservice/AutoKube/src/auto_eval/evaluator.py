# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import yaml
import re
import os
from tqdm import tqdm
from ..api.cloudgpt_aoai import get_chat_completion
from .slo_checker import checkSLO

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

class Evaluator:
    """
    A class to evaluate an experiment instance by analyzing chat logs and validating results 
    based on predefined autonomous levels and evaluation configurations.
    """
    
    def __init__(self, instance: str, namespace: str, component: str):
        """
        Initialize the Evaluator.

        Parameters:
        - instance (str): The name of the experiment instance.
        - namespace (str): The namespace of the experiment.
        - component (str): The component under evaluation.
        """
        self.instance = instance
        self.namespace = namespace
        self.component = component

    def errorDetection(self, markdown_content: str) -> str:
        """
        Perform error detection on the given markdown content.

        Parameters:
        - markdown_content (str): The content of the markdown file to analyze.

        Returns:
        - str: The result of the error detection.
        """
        system_message = yaml.load(
            open(os.path.join(current_path, 'auto_eval_conf', 'error_detection.yaml')), 
            Loader=yaml.FullLoader
        )['prompt']

        chat_message = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": "The chatlog is as follows:"},
            {"role": "user", "content": markdown_content}
        ]

        engine = "gpt-4-turbo-20240409"
        response = get_chat_completion(engine=engine, messages=chat_message)
        return response.choices[0].message.content.strip()

    def callEvaluator(self):
        """
        Call the evaluator based on the autonomous level of the experiment instance.

        Returns:
        - tuple or bool: Evaluation results for levels 3, 4, and 5 or a single evaluation result for lower levels.
        """
        with open(os.path.join(current_path, 'auto_eval_conf', f'{self.instance}.yaml')) as file:
            autonomous_level = yaml.load(file, Loader=yaml.FullLoader)['level']
            
            if autonomous_level < 3:
                return self.agentEvaluator(checkpoint=self.instance)
            else:
                l3_result = self.agentEvaluator(checkpoint="l3")
                l4_result = self.agentEvaluator(checkpoint="l4")
                l5_result = self.sloEvaluator()
                return l3_result, l4_result, l5_result

    def agentEvaluator(self, checkpoint: str):
        """
        Evaluate the experiment using the agent evaluator configuration.

        Parameters:
        - checkpoint (str): The evaluation checkpoint (e.g., 'l3', 'l4').

        Returns:
        - tuple: (Evaluation result, average steps, error detection result).
        """
        system_message = yaml.load(
            open(os.path.join(current_path, 'auto_eval_conf', f'{checkpoint}.yaml')), 
            Loader=yaml.FullLoader
        )['prompt']

        markdown_file_path = os.path.join(
            current_path, '..', 'results/Experiment', f'{self.namespace}/{self.instance}.md'
        )
        with open(markdown_file_path, 'r', encoding='utf-8') as file:
            markdown_content = file.read()

        chat_message = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": "The chatlog is as follows:"},
            {"role": "user", "content": markdown_content}
        ]

        engine = "gpt-4-turbo-20240409"
        true_count = 0
        false_count = 0
        step_avg = 0

        # Evaluate the response 10 times
        for _ in tqdm(range(10), desc="Evaluating"):
            response = get_chat_completion(engine=engine, messages=chat_message)
            response_content = response.choices[0].message.content.strip()
            print(response_content)

            # Count TRUE and FALSE responses
            if re.search(r'\$TRUE\$', response_content, re.IGNORECASE):
                true_count += 1
            elif re.search(r'\$FALSE\$', response_content, re.IGNORECASE):
                false_count += 1
            else:
                raise ValueError("The model did not return a clear TRUE or FALSE response.")

            # Extract step count from the response
            match = re.search(r'\$(\d+)\$', response_content)
            if match:
                step_avg += int(match.group(1))
            else:
                raise ValueError("The model did not calculate steps.")

        step_avg //= 10
        error_detection_result = self.errorDetection(markdown_content)

        # Return evaluation result
        return (True if true_count > false_count else False, step_avg, error_detection_result)

    def sloEvaluator(self) -> bool:
        """
        Evaluate the experiment's Service Level Objectives (SLO).

        Returns:
        - bool: The result of the SLO evaluation.
        """
        return checkSLO()

if __name__ == '__main__':
    evaluator = Evaluator('pod_failure', 'sock-shop', 'catalogue')
    print(evaluator.callEvaluator())
