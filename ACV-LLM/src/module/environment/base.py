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
    """
    Abstract base class for managing deployment environments. Provides common methods for resource customization
    and pod readiness checks, with abstract methods for setup and teardown that must be implemented by subclasses.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the environment manager with project-specific configurations.
        """
        self.deployment: str = ""
        self.project = global_config['project']['name']
        self.project_path = global_config['project']['path']
        self.namespace = global_config['project']['namespace']
        self.unhealthy_pods: int = 0
        super().__init__(**kwargs)

    @abstractmethod
    def setup(self, config_fpath: Union[str, None]):
        """
        Abstract method to set up the environment.
        Must be implemented by subclasses.
        """
        raise NotImplementedError('Method setup() must be implemented.')

    @abstractmethod
    def teardown(self):
        """
        Abstract method to tear down the environment.
        Must be implemented by subclasses.
        """
        raise NotImplementedError('Method teardown() must be implemented.')

    def customize_resource(self, config_fpath: Union[str, None]):
        """
        Customize Kubernetes resources based on a configuration file.

        Parameters:
        - config_fpath (Union[str, None]): Path to the YAML configuration file specifying resource customizations.

        The configuration can include:
        - 'delete': List of deployments to delete.
        - 'create': List of deployment YAML file paths to apply.
        - 'modify': List of deployment modifications (add, delete, replace).
        """
        config = load_yaml(config_fpath)
        resource_config = config['environment']
        self.unhealthy_pods = resource_config.get('unhealthy_pods', 0)

        # Delete resources
        if 'delete' in resource_config:
            for deployment in resource_config['delete']:
                subprocess.run(
                    ['kubectl', 'delete', 'deployment', deployment, '-n', self.namespace],
                    check=True,
                )

        # Create resources
        if 'create' in resource_config:
            for deployment_fpath in resource_config['create']:
                subprocess.run(
                    ['kubectl', 'apply', '-f', deployment_fpath, '-n', self.namespace],
                    check=True,
                )

        # Modify resources
        if 'modify' in resource_config:
            for deployment_info in resource_config['modify']:
                deployment = deployment_info['deployment']

                # Delete paths
                if 'delete' in deployment_info:
                    for item in deployment_info['delete']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n',
                            self.namespace, '-p', f'{{"op": "remove", "path": "{item}"}}'
                        ]
                        subprocess.run(command, check=True)

                # Add new paths
                if 'create' in deployment_info:
                    for item in deployment_info['create']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n', self.namespace, '--type=json',
                            '-p', f'[{{"op": "add", "path": "{item["path"]}", "value": "{item["value"]}"}}]'
                        ]
                        subprocess.run(command, check=True)

                # Modify existing paths
                if 'modify' in deployment_info:
                    for item in deployment_info['modify']:
                        command = [
                            'kubectl', 'patch', 'deployment', deployment, '-n', self.namespace, '--type=json',
                            '-p', f'[{{"op": "replace", "path": "{item["path"]}", "value": "{item["value"]}"}}]'
                        ]
                        subprocess.run(command, check=True)

    def check_pods_ready(self, interval: int = 15):
        """
        Check if all pods in the namespace are ready.

        Parameters:
        - interval (int): Interval in seconds between readiness checks (default: 15).
        """
        try:
            self.info('Checking pod status for readiness...')
            ready_cnt = 0
            total_cnt = int(1e9)  # Placeholder for initial total count
            while ready_cnt + self.unhealthy_pods < total_cnt:
                jsonpath = r'{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'
                result = subprocess.run(
                    ['kubectl', 'get', 'pods', '-n', self.namespace, f'-o=jsonpath={jsonpath}'],
                    capture_output=True, text=True
                ).stdout.strip()

                lines = result.split('\n')
                ready_cnt = sum(1 for line in lines if line.strip().lower() == 'true')
                total_cnt = len(lines)

                self.info(f'Pods Ready: {ready_cnt}/{total_cnt}')
                time.sleep(interval)

        except KeyboardInterrupt:
            self.warning('User interrupted the readiness check process.')
            return

        self.info('All pods are ready.')
