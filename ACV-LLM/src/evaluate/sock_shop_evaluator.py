import os
import json
import subprocess
import requests

from typing import Dict
import re
from .base import Evaluator
from .markdown_evaluator import _load_markdown2chat_message, _call_llm4judge, _calculate_steps

class SockShopEvaluator(Evaluator):
    """ACV Auto evaluator for Sock Shop application."""
    def __init__(self):
        self.project = 'sock-shop'
        self.hash_code = ''
        super().__init__()

    def evaluate(self, test_case: str, hash_code: str, **kwargs: dict):
        """
        Evaluate the test case in Sok Shop application.

        Args:
            test_case (str): The test case to evaluate.
            hash_code (str): The hash code of the test case.
            **kwargs (dict): The keyword arguments to pass to the test case.

        Raises:
            NotImplementedError: If the test case is not implemented.

        Returns:
            bool: The evaluation result
        """
        self.load_test_case(test_case)
        self.hash_code = hash_code
        func = getattr(self, f"_evaluate_{test_case}", None)
        if func is None:
            raise NotImplementedError(f"Test case {test_case} is not implemented.")
        return func(**kwargs)
    
    def evaluate_level_3_4_5(self, instance: str) -> dict:
        markdown_file_path = f"results/{instance}-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'level_3_prompt')
        l3_result = _call_llm4judge(chat_message, self.hash_code, 'level_3_judge')

        chat_message = _load_markdown2chat_message(markdown_file_path, 'level_4_prompt')
        l4_result = _call_llm4judge(chat_message, self.hash_code, 'level_4_judge')

        step_cnts = _calculate_steps(markdown_file_path)

        return {
            "L3 Assessment": l3_result,
            "L4 Assessment": l4_result,
            "Step Counts": step_cnts
        }

    def _calculate_steps(self, markdown_file_path: str) -> Dict[str, int]:
        """Calculate the number of steps for each round in the given markdown file."""
        # Load the markdown content
        if os.path.exists(markdown_file_path):
            with open(markdown_file_path, 'r', encoding='utf-8') as file:
                markdown_content = file.read()
        else:
            raise FileNotFoundError(f"File not found: {markdown_file_path}")

        # Count the number of steps for each round
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
    Level 1 test cases
    '''
    def _evaluate_update_deployment(self, **kwargs) -> bool:
        """Evaluate the update deployment test case."""
        try:
            env = subprocess.run(
                [
                    "kubectl", "get", "pods", "-n", self.namespace, "-l", f"name={self.component}",
                    "-o", r"jsonpath='{.items[*].spec.containers[*].env}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            if env is not None:
                env = json.loads(env)
                for item in env:
                    if item['name'] == 'logger_flag' and item['value'] == 'true':
                        return True
        except Exception as e:
            print(e)
        return False
    
    def _evaluate_create_deployment(self) -> bool:
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "deployment", self.component, "-n", self.namespace
                ],
                check=False, capture_output=True, text=True
            )

            if result.returncode == 0:
                return True
        except Exception as e:
            print(e)
        return False
    
    def _evaluate_rollback(self, image_version: str = "0.3.4") -> bool:
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "pods", "-n", self.namespace, "-l", f"name={self.component}",
                    "-o", r"jsonpath='{.items[*].spec.containers[*].image}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            
            if result:
                images = result.split()
                for image in images:
                    if image.endswith(image_version):
                        return True
        except Exception as e:
            print(e)
        return False
    
    def _evaluate_manual_scaling(self, replicas: int = 3) -> bool:
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "deployment", "-n", self.namespace, self.component,
                    "-o", r"jsonpath='{.spec.replicas}'"
                ],
                check=True, capture_output=True, text=True
            ).stdout.strip('\'')
            if result:
                return int(result) == replicas
        except Exception as e:
            print(e)
        return False
    
    def _evaluate_restart(self) -> bool:
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "pods", "-n", self.namespace,
                    "--no-headers"
                ],
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
                pod_data = pod_line.split()
                pod_name = pod_data[0]
                pod_age_str = pod_data[-1]

                if 'm' in pod_age_str:
                    pod_age_minutes = int(pod_age_str.rstrip('m'))
                    if pod_age_minutes >= 2:
                        return False
                elif 's' in pod_age_str:
                    pod_age_seconds = int(pod_age_str.rstrip('s'))
                    if pod_age_seconds >= 120:
                        return False
                else:
                    return False

            return True

        except Exception as e:
            print(f"An error occurred: {e}")

        return False
    
    def _evaluate_metric_collection_1(self) -> bool:
        markdown_file_path = "results/sock-shop/metric_collection_1-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'metric_collection_1_prompt')

        return _call_llm4judge(chat_message, self.hash_code, "metric_collection_1")
    
    def _evaluate_metric_collection_2(self) -> bool:
        markdown_file_path = "results/sock-shop/metric_collection_2-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'metric_collection_2_prompt')

        return _call_llm4judge(chat_message, self.hash_code, "metric_collection_2")
    
    '''
    Level 2 test cases
    '''  
    def _evaluate_healthy_check(self) -> bool:
        markdown_file_path = "results/sock-shop/healthy_check-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'healthy_check_prompt')

        return _call_llm4judge(chat_message, self.hash_code, "healthy_check")

    def _evaluate_performance_check(self) -> bool:
        markdown_file_path = "results/sock-shop/performance_check-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'performance_check_prompt')

        return _call_llm4judge(chat_message, self.hash_code, "performance_check")

    def _evaluate_auto_scaling(self) -> bool:
        markdown_file_path = "results/sock-shop/auto_scaling-stable.md"
        chat_message = _load_markdown2chat_message(markdown_file_path, 'auto_scaling_prompt')

        return _call_llm4judge(chat_message, self.hash_code, "auto_scaling")

    def _query_promQL(self, promQL: str, duration: str = '2m', step: str = '1m') -> list:
        from src.agent.tool_functions_for_maintainer import query_prometheus

        try:
            return query_prometheus(promQL, duration=duration, step=step)
        except requests.exceptions.RequestException as e:
            print(f"Error querying Prometheus: {e}")
        except Exception as e:
            print(f"General error: {e}")
        return []

    def _evaluate_reduce_latency(self) -> bool:
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
    Level 3, 4, 5 test cases
    '''
    def _evaluate_cpu_stress(self) -> dict:
        return self.evaluate_level_3_4_5("cpu_stress")

    def _evaluate_memory_stress(self) -> dict:
        return self.evaluate_level_3_4_5("memory_stress")

    def _evaluate_pod_failure(self) -> dict:
        return self.evaluate_level_3_4_5("pod_failure")

    def _evaluate_rasing_traffic(self) -> dict:
        return self.evaluate_level_3_4_5("rasing_traffic")
    
    def _evaluate_limit_bandwidth(self) -> dict:
        return self.evaluate_level_3_4_5("limit_bandwidth")

if __name__ == "__main__":
    evaluator = SockShopEvaluator()
    print(evaluator.evaluate("update_deployment"))