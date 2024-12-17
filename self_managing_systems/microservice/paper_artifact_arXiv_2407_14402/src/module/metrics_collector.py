# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from .base import Base
from .utils import get_resource_limit_by_pod, get_resource_usage_by_pod, format_resource_data, load_config

config = load_config()

class MetricsCollector(Base):
    """
    MetricsCollector provides methods to collect and analyze resource metrics for Kubernetes pods,
    such as resource limits, usage, and stability checks.
    """

    def __init__(self, test_case: str = None, **kwargs):
        """
        Initialize the MetricsCollector.

        Args:
        - test_case (str, optional): The test case name to load. Default is None.
        - kwargs (dict): Additional arguments for the Base class.
        """
        super().__init__(**kwargs)
        self.timer = None
        self.interval = 15  # Default collection interval in seconds
        if test_case:
            self.load_test_case(test_case)

    def get_resource_limit_by_pod(self, namespace: str = 'default', pod_name: str = '') -> dict:
        """
        Retrieve resource limits for a specific pod.

        Args:
        - namespace (str, optional): The namespace of the pod. Default is 'default'.
        - pod_name (str, optional): The name of the pod. Default is ''.

        Returns:
        - dict: Resource limits for the specified pod.
        """
        return get_resource_limit_by_pod(namespace=namespace, pod_name=pod_name)

    def get_resource_usage_by_pod(self, namespace: str = 'default', pod_name: str = '') -> dict:
        """
        Retrieve resource usage for a specific pod.

        Args:
        - namespace (str, optional): The namespace of the pod. Default is 'default'.
        - pod_name (str, optional): The name of the pod. Default is ''.

        Returns:
        - dict: Resource usage for the specified pod.
        """
        return get_resource_usage_by_pod(namespace=namespace, pod_name=pod_name)

    def get_resource_usage_percentage_by_pod(self, namespace: str = 'default', pod_name: str = '') -> dict:
        """
        Calculate the resource usage percentage for a specific pod.

        Args:
        - namespace (str, optional): The namespace of the pod. Default is 'default'.
        - pod_name (str, optional): The name of the pod. Default is ''.

        Returns:
        - dict: Resource usage percentages for CPU and memory.
        """
        limit = self.get_resource_limit_by_pod(namespace=namespace, pod_name=pod_name)
        usage = self.get_resource_usage_by_pod(namespace=namespace, pod_name=pod_name)
        limit = format_resource_data(limit)
        usage = format_resource_data(usage)
        result = {}

        for pod, limits in limit.items():
            if pod not in usage:
                result[pod] = {
                    'cpu': 'N/A',
                    'memory': 'N/A'
                }
            else:
                result[pod] = {
                    'cpu': (usage[pod]['cpu'] / limits['cpu']) * 100,
                    'memory': (usage[pod]['memory'] / limits['memory']) * 100
                }
        return result

    def check_stable_state_by_pod(self, namespace: str = 'default', pod_name: str = '') -> bool:
        """
        Check if the pod is in a stable state based on resource usage.

        Args:
        - namespace (str, optional): The namespace of the pod. Default is 'default'.
        - pod_name (str, optional): The name of the pod. Default is ''.

        Returns:
        - bool: True if the pod is in a stable state, False otherwise.
        """
        min_usage = float(config['mode2usage'][self.mode]['min']['cpu'])
        max_usage = float(config['mode2usage'][self.mode]['max']['cpu'])
        usage = self.get_resource_usage_percentage_by_pod(namespace=namespace, pod_name=pod_name)

        if not usage:
            return True  # No usage data implies stable state
        
        for pod, metrics in usage.items():
            self.info(
                'Pod: {}, CPU Usage: {:.2f}%, Min Usage: {:.2f}%, Max Usage: {:.2f}%'.format(
                    pod, metrics['cpu'], min_usage, max_usage
                )
            )
            if metrics['cpu'] == 'N/A' or metrics['memory'] == 'N/A':
                continue  # Skip unavailable metrics
            if metrics['cpu'] > max_usage or metrics['cpu'] < min_usage:
                return False
        return True
