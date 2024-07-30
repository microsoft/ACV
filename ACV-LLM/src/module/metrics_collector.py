# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from .base import Base
from .utils import get_resource_limit_by_pod, get_resource_usage_by_pod, format_resource_data, load_config


config = load_config()

class MetricsCollector(Base):

    def __init__(self, test_case: str = None, **kwargs):
        super().__init__(**kwargs)
        self.timer = None
        self.interval = 15
        if test_case:
            self.load_test_case(test_case)

    def get_resource_limit_by_pod(self, namespace:str='default', pod_name:str=''):
        '''
        Get resource limits by pod using kubectl
        - param namespace: str, namespace of the pod
        - param pod_name: str, name of the pod
        - return: dict, pod resource limits
        '''
        return get_resource_limit_by_pod(namespace=namespace, pod_name=pod_name)

    def get_resource_usage_by_pod(self, namespace:str='default', pod_name:str=''):
        '''
        Get resource usage by pod using kubectl
        - param namespace: str, namespace of the pod
        - param pod_name: str, name of the 
        - return: dict, pod resource usage
        '''
        return get_resource_usage_by_pod(namespace=namespace, pod_name=pod_name)

    def get_resource_usage_percentage_by_pod(self, namespace:str='default', pod_name:str=''):
        '''
        Get resource usage percentage by pod
        - param namespace: str, namespace of the pod
        - param pod_name: str, name of the pod
        - return: dict, resource usage percentage
        Note: resource usage contains all pods in the namespace, where resource limit only contains the specified pods
        '''
        limit = self.get_resource_limit_by_pod(namespace=namespace, pod_name=pod_name)
        usage = self.get_resource_usage_by_pod(namespace=namespace, pod_name=pod_name)
        limit = format_resource_data(limit)
        usage = format_resource_data(usage)
        result = {}
        for k, v in limit.items():
            if k not in usage:
                result[k] = {
                    'cpu': 'N/A',
                    'memory': 'N/A'
                }
            else:
                result[k] = {
                    'cpu': usage[k]['cpu'] / v['cpu'] * 100,
                    'memory': usage[k]['memory'] / v['memory'] * 100
                }
        return result

    def check_stable_state_by_pod(self, namespace:str='default', pod_name:str=''):
        '''
        Check if the pod is in a stable state
        - param namespace: str, namespace of the pod
        - param pod_name: str, name of the pod
        - param threshold: float, threshold of the resource usage
        - return: bool, True if the pod is in a stable state, False otherwise
        '''
        min_usage = float(config['mode2usage'][self.mode]['min']['cpu'])
        max_usage = float(config['mode2usage'][self.mode]['max']['cpu'])
        usage = self.get_resource_usage_percentage_by_pod(namespace=namespace, pod_name=pod_name)
        if len(usage) == 0:
            return True
        
        for k, v in usage.items():
            self.info('cpu_usage: {:.2f}, min_usage: {:.2f}, max_usage: {:.2f}'.format(v['cpu'], min_usage, max_usage))
            if v['cpu'] == 'N/A' or v['memory'] == 'N/A':
                continue
            if v['cpu'] > max_usage or v['cpu'] < min_usage:
                return False
        return True