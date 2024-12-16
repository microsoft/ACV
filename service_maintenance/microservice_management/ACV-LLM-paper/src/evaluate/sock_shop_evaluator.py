# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import json
import subprocess
import requests
from typing import Dict
import re
from .base import Evaluator
from .markdown_evaluator import _load_markdown2chat_message, _call_llm4judge, _calculate_steps

class SockShopEvaluator(Evaluator):
    """
    ACV Auto evaluator for the Sock Shop application.

    This class provides methods to evaluate deployment, scaling, performance, and other 
    functionalities of the Sock Shop microservice application.
    """

    def __init__(self):
        """
        Initialize the SockShopEvaluator.

        Attributes:
        - project (str): The name of the project being evaluated.
        - hash_code (str): A unique identifier for the test case evaluation.
        """
        self.project = 'sock-shop'
        self.hash_code = ''
        super().__init__()

    def evaluate(self, test_case: str, hash_code: str, **kwargs: dict):
        """
        Evaluate a specified test case in the Sock Shop application.

        Parameters:
        - test_case (str): The name of the test case to evaluate.
        - hash_code (str): A unique hash code for the test case.
        - kwargs (dict): Additional arguments for the test case evaluation.

        Returns:
        - bool: True if the evaluation succeeds, otherwise False.

        Raises:
        - NotImplementedError: If the test case is not implemented.
        """
        self.hash_code = hash_code
        func = getattr(self, f"_evaluate_{test_case}", None)
        if func is None:
            raise NotImplementedError(f"Test case {test_case} is not implemented.")
        return func(**kwargs)

    def evaluate_level_3_4_5(self, instance: str) -> dict:
        """
        Evaluate test cases for levels 3, 4, and 5.

        Parameters:
        - instance (str): The test instance to evaluate.

        Returns:
        - dict: A dictionary containing assessments and step counts for the test instance.
        """
        markdown_file_path = f"results/{instance}-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'level_3_prompt')
        l3_result = _call_llm4judge(chat_message, self.hash_code, 'level_3_judge')

        chat_message = _load_markdown2chat_message(markdown_file_path, 'level_4_prompt')
        l4_result = _call_llm4judge(chat_message, self.hash_code, 'level_4_judge')

        step_counts = _calculate_steps(markdown_file_path)

        return {
            "L3 Assessment": l3_result,
            "L4 Assessment": l4_result,
            "Step Counts": step_counts
        }

    def _calculate_steps(self, markdown_file_path: str) -> Dict[str, int]:
        """
        Calculate the number of steps for each round in a given markdown file.

        Parameters:
        - markdown_file_path (str): Path to the markdown file.

        Returns:
        - dict: A dictionary mapping each round to its corresponding step count.

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

    '''
    Level 1 Test Cases
    '''

    def _evaluate_update_deployment(self, **kwargs) -> bool:
        """
        Evaluate whether a deployment update has been correctly applied.

        Parameters:
        - kwargs (dict): Additional arguments for the evaluation.

        Returns:
        - bool: True if the logger flag is set to 'true', otherwise False.
        """
        try:
            env = subprocess.run(
                [
                    "kubectl", "get", "pods", "-n", self.project, "-l", f"name={self.component}",
                    "-o", r"jsonpath='{.items[*].spec.containers[*].env}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            
            if env:
                env_data = json.loads(env)
                for item in env_data:
                    if item.get('name') == 'logger_flag' and item.get('value') == 'true':
                        return True
        except Exception as e:
            print(f"Error in update deployment evaluation: {e}")
        return False

    def _evaluate_create_deployment(self) -> bool:
        """
        Check whether the deployment exists in the specified namespace.

        Returns:
        - bool: True if the deployment exists, otherwise False.
        """
        try:
            result = subprocess.run(
                ["kubectl", "get", "deployment", self.component, "-n", self.project],
                check=False, capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error in create deployment evaluation: {e}")
        return False

    def _evaluate_rollback(self, image_version: str = "0.3.4") -> bool:
        """
        Check whether the deployment has rolled back to the specified image version.

        Parameters:
        - image_version (str): The expected image version after rollback.

        Returns:
        - bool: True if the rollback succeeded, otherwise False.
        """
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "pods", "-n", self.project, "-l", f"name={self.component}",
                    "-o", r"jsonpath='{.items[*].spec.containers[*].image}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            
            if result:
                images = result.split()
                return any(image.endswith(image_version) for image in images)
        except Exception as e:
            print(f"Error in rollback evaluation: {e}")
        return False

    def _evaluate_manual_scaling(self, replicas: int = 3) -> bool:
        """
        Evaluate whether the deployment has been manually scaled to the expected number of replicas.

        Parameters:
        - replicas (int): The expected number of replicas. Default is 3.

        Returns:
        - bool: True if the scaling matches the expected number, otherwise False.
        """
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "deployment", "-n", self.project, self.component,
                    "-o", r"jsonpath='{.spec.replicas}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            return result and int(result) == replicas
        except Exception as e:
            print(f"Error in manual scaling evaluation: {e}")
        return False

    def _evaluate_restart(self) -> bool:
        """
        Evaluate whether the pod restart behavior is functioning as expected.

        Returns:
        - bool: True if the pods restarted recently, otherwise False.
        """
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", self.project, "--no-headers"],
                check=True, capture_output=True, text=True
            ).stdout.strip()

            if not result:
                print("No pods found in the namespace.")
                return False

            pod_lines = [line for line in result.splitlines() if 'catalogue' in line]
            if not pod_lines:
                print("No 'catalogue' pods found.")
                return False

            for pod_line in pod_lines:
                pod_age_str = pod_line.split()[-1]  # Get the age column
                if 'm' in pod_age_str and int(pod_age_str.rstrip('m')) >= 2:
                    return False
                elif 's' in pod_age_str and int(pod_age_str.rstrip('s')) >= 120:
                    return False

            return True
        except Exception as e:
            print(f"Error in restart evaluation: {e}")
        return False
    
    def _evaluate_metric_collection_1(self) -> bool:
        """
        Evaluate the first metric collection scenario for the Sock Shop application.

        Returns:
        - bool: True if the evaluation succeeds, otherwise False.
        """
        markdown_file_path = "results/sock-shop/metric_collection_1-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'metric_collection_1_prompt')
        return _call_llm4judge(chat_message, self.hash_code, "metric_collection_1")

    def _evaluate_metric_collection_2(self) -> bool:
        """
        Evaluate the second metric collection scenario for the Sock Shop application.

        Returns:
        - bool: True if the evaluation succeeds, otherwise False.
        """
        markdown_file_path = "results/sock-shop/metric_collection_2-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'metric_collection_2_prompt')
        return _call_llm4judge(chat_message, self.hash_code, "metric_collection_2")
    
    '''
    Level 2 Test Cases
    '''
    def _evaluate_healthy_check(self) -> bool:
        """
        Evaluate the health check scenario for the Sock Shop application.

        Returns:
        - bool: True if the health check passes, otherwise False.
        """
        markdown_file_path = "results/sock-shop/healthy_check-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'healthy_check_prompt')
        return _call_llm4judge(chat_message, self.hash_code, "healthy_check")

    def _evaluate_performance_check(self) -> bool:
        """
        Evaluate the performance of the Sock Shop application.

        Returns:
        - bool: True if the performance meets the criteria, otherwise False.
        """
        markdown_file_path = "results/sock-shop/performance_check-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'performance_check_prompt')
        return _call_llm4judge(chat_message, self.hash_code, "performance_check")

    def _evaluate_auto_scaling(self) -> bool:
        """
        Evaluate the auto-scaling functionality of the Sock Shop application.

        Returns:
        - bool: True if auto-scaling is working as expected, otherwise False.
        """
        markdown_file_path = "results/sock-shop/auto_scaling-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'auto_scaling_prompt')
        return _call_llm4judge(chat_message, self.hash_code, "auto_scaling")

    def _query_promQL(self, promQL: str, duration: str = '2m', step: str = '1m') -> list:
        """
        Query Prometheus with the specified promQL query.

        Parameters:
        - promQL (str): The PromQL query to execute.
        - duration (str): The duration for which to query the data. Default is '2m'.
        - step (str): The interval between data points in the query. Default is '1m'.

        Returns:
        - list: The result of the PromQL query.

        Raises:
        - requests.exceptions.RequestException: If an error occurs while querying Prometheus.
        """
        from src.agent.tool_functions_for_maintainer import query_prometheus

        try:
            return query_prometheus(promQL, duration=duration, step=step)
        except requests.exceptions.RequestException as e:
            print(f"Error querying Prometheus: {e}")
        except Exception as e:
            print(f"General error: {e}")
        return []

    def _evaluate_reduce_latency(self) -> bool:
        """
        Evaluate if the P99 latency of the Sock Shop catalogue service is below 300ms.

        Returns:
        - bool: True if the P99 latency is under 300ms, otherwise False.
        """
        promQL = 'histogram_quantile(0.99, sum(rate(request_duration_seconds_bucket{name="catalogue"}[1m])) by (name, le))'
        duration = '2m'
        step = '1m'
        result = self._query_promQL(promQL, duration, step)
        if not result:
            return False

        p99_latency = max(result, key=lambda x: x[1])[1]
        if p99_latency and p99_latency < 0.3:
            print(f"P99 latency is under 300 ms: {p99_latency * 1000:.2f} ms")
            return True
        else:
            print(f"P99 latency is above 300 ms: {p99_latency * 1000:.2f} ms")
            return False

    def _evaluate_reduce_resource_usage(self) -> bool:
        """
        Evaluate if the CPU usage of the Sock Shop catalogue service is under 30% of total CPU usage.

        Returns:
        - bool: True if the CPU usage is below 30%, otherwise False.
        """
        promQL = '''
        sum(irate(process_cpu_seconds_total{job="sock-shop/catalogue"}[1m]))
        /
        sum(irate(process_cpu_seconds_total{job=~"sock-shop/.*"}[1m])) * 100
        '''
        duration = '2m'
        step = '1m'
        result = self._query_promQL(promQL, duration, step)
        if not result:
            return False

        cpu_usage_percentage = max(result, key=lambda x: x[1])[1]
        if cpu_usage_percentage and cpu_usage_percentage < 30:
            print(f"Catalogue CPU usage is under 30% of total sock-shop: {cpu_usage_percentage:.2f}%")
            return True
        else:
            print(f"Catalogue CPU usage is above 30% of total sock-shop: {cpu_usage_percentage:.2f}%")
            return False

    '''
    Level 3, 4, 5 Test Cases
    '''
    def _evaluate_cpu_stress(self) -> dict:
        """
        Evaluate the CPU stress test for the Sock Shop application.

        Returns:
        - dict: The results of levels 3, 4, and 5 assessments.
        """
        return self.evaluate_level_3_4_5("cpu_stress")

    def _evaluate_memory_stress(self) -> dict:
        """
        Evaluate the memory stress test for the Sock Shop application.

        Returns:
        - dict: The results of levels 3, 4, and 5 assessments.
        """
        return self.evaluate_level_3_4_5("memory_stress")

    def _evaluate_pod_failure(self) -> dict:
        """
        Evaluate the pod failure scenario for the Sock Shop application.

        Returns:
        - dict: The results of levels 3, 4, and 5 assessments.
        """
        return self.evaluate_level_3_4_5("pod_failure")

    def _evaluate_rasing_traffic(self) -> dict:
        """
        Evaluate the rising traffic scenario for the Sock Shop application.

        Returns:
        - dict: The results of levels 3, 4, and 5 assessments.
        """
        return self.evaluate_level_3_4_5("rasing_traffic")

    def _evaluate_limit_bandwidth(self) -> dict:
        """
        Evaluate the bandwidth limitation scenario for the Sock Shop application.

        Returns:
        - dict: The results of levels 3, 4, and 5 assessments.
        """
        return self.evaluate_level_3_4_5("limit_bandwidth")

if __name__ == "__main__":
    evaluator = SockShopEvaluator()
    print(evaluator.evaluate("update_deployment"))
