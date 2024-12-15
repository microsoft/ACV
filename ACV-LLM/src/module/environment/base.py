# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import time
import subprocess

from abc import ABC, abstractmethod
from typing import Union

from ..base import Base
from ..utils import load_config, load_yaml

global_config = load_config()

class EnvironmentManager(ABC, Base):
    
    def __init__(self, **kwargs) -> None:
        self.deployment: str
        self.project = global_config['project']['name']
        self.project_path = global_config['project']['path']
        self.namespace = global_config['project']['namespace']
        self.unhealthy_pods: int = 0
        super().__init__(**kwargs)

    @abstractmethod
    def setup(self, config_fpath: Union[str, None]):
        raise NotImplementedError('Method setup() must be implemented.')

    @abstractmethod
    def teardown(self):
        raise NotImplementedError('Method teardown() must be implemented.')

    def customize_resource(self, config_fpath: Union[str, None]):
        config = load_yaml(config_fpath)
        resource_config = config['environment']
        self.unhealthy_pods = resource_config['unhealthy_pods']
        if 'delete' in resource_config:
            for deployment in resource_config['delete']:
                subprocess.run(
                    ['kubectl', 'delete', 'deployment', deployment, '-n', self.namespace],
                    check=True,
                )
        if 'create' in resource_config:
            for deployment_fpath in resource_config['create']:
                subprocess.run(
                    ['kubectl', 'apply', '-f', deployment_fpath, '-n', self.namespace],
                    check=True,
                )
        if 'modify' in resource_config:
            for deployment_info in resource_config['modify']:
                deployment = deployment_info['deployment']
                if 'delete' in deployment_info:
                    for item in deployment_info['delete']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n', 
                            self.namespace, '-p', f'{{"op": "remove", "path": "{item}"}}'
                        ]
                        subprocess.run(command, check=True)
                if 'create' in deployment_info:
                    for item in deployment_info['create']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n', self.namespace, '--type=json', 
                            '-p', f'[{{"op": "add", "path": "{item["path"]}", "value": "{item["value"]}"}}]'
                        ]
                        subprocess.run(command, check=True)
                if 'modify' in deployment_info:
                    for item in deployment_info['modify']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n', self.namespace, '--type=json', 
                            '-p', f'[{{"op": "replace", "path": "{item["path"]}", "value": "{item["value"]}"}}]'
                        ]
                        subprocess.run(command, check=True)

    def check_pods_ready(self, interval: int = 15):
        '''
        Check if all pods are ready in environment
        - param interval: int, interval of checking in seconds
        '''
        try:
            self.info('checking pods status for ready...')
            ready_cnt = 0
            total_cnt = 1e9
            while ready_cnt + self.unhealthy_pods < total_cnt:
                jsonpath = r'{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'
                result = subprocess.run(
                    ['kubectl', 'get', 'pods', '-n', global_config['project']['namespace'], f'-o=jsonpath={jsonpath}'], 
                    capture_output=True, text=True
                ).stdout.strip()
                lines = result.split('\n')
                ready_cnt = sum(1 for line in lines if line.strip().lower() == 'true')
                total_cnt = len(lines)
                self.info('Pods Ready: {}/{}'.format(ready_cnt, total_cnt))
                time.sleep(interval)
        except KeyboardInterrupt:
            self.warning('User interrupted the checking process.')
            return
        self.info('All pods are ready.')