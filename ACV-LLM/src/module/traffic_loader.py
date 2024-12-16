# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import subprocess
from typing import Literal

from .utils import fill_content_in_yaml, load_config, load_yaml
from .base import Base

global_config = load_config()

class TrafficLoader(Base):
    """
    TrafficLoader is responsible for managing traffic loads for components in a Kubernetes environment.
    It supports different traffic backends and traffic modes to simulate various workloads.
    """

    def __init__(
        self,
        component: str = '',
        namespace: str = 'default',
        mode: Literal['light', 'moderate', 'heavy'] = 'moderate',
        test_case: str = None,
        **kwargs: dict
    ):
        """
        Initialize the TrafficLoader class.

        Args:
        - component (str): The name of the component for which traffic is to be loaded.
        - namespace (str): The namespace of the component.
        - mode (Literal['light', 'moderate', 'heavy']): The traffic mode. Default is 'moderate'.
        - test_case (str): The test case identifier. If set, it overrides component, namespace, and mode.
        - kwargs (dict): Additional parameters, such as backend configuration.
        """
        super().__init__(**kwargs)

        if test_case:
            self.info(f"Loading test case: {test_case}")
            self.load_test_case(test_case)
        else:
            self.component = component
            self.namespace = namespace
            self.mode = mode
        
        self.test_case = test_case
        self.backend = global_config['traffic_loader']['backend']
        self.external_args = kwargs

        if 'backend' in self.external_args:
            self.backend = self.external_args['backend']
        
        if self.backend not in ['locust']:
            raise ValueError(f"Backend {self.backend} is not supported")

    def _locust_traffic(self) -> str:
        """
        Generate traffic configuration for the Locust backend.

        Returns:
        - str: The traffic configuration in YAML format.
        """
        args: dict = global_config['workload'][self.mode]
        for key in ['users', 'spawn_rate']:
            if self.external_args.get(key, None):
                args[key] = self.external_args[key]
        args.update({
            'component': self.component,
            'namespace': self.namespace,
        })
        traffic = fill_content_in_yaml(global_config['traffic_loader']['template_path'], args)
        return traffic

    def get_traffic(self) -> str:
        """
        Get the traffic configuration for the specified component.

        Returns:
        - str: The traffic configuration in YAML format.
        """
        return self.__getattribute__(f'_{self.backend}_traffic')()

    def start(self):
        """
        Start traffic loading for the specified component.
        """
        traffic = self.get_traffic()
        subprocess.Popen(
            ['kubectl', 'apply', '-f', '-'],
            stdin=subprocess.PIPE,
            text=True
        ).communicate(traffic)
        self.info(f"Traffic load for {self.component} is set to {self.mode} mode")

    def stop(self):
        """
        Stop and remove traffic for the specified component.
        """
        subprocess.run(
            ['kubectl', 'delete', '-f', global_config['traffic_loader']['template_path']],
            check=True
        )
        self.info(f"Traffic loaded for {self.component} is removed")
