# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import subprocess
from typing import Literal

from .utils import fill_content_in_yaml, load_config, load_yaml
from .base import Base


global_config = load_config()

class TrafficLoader(Base):

    def __init__(self, component: str = '', namespace: str = 'default', mode: Literal['light', 'moderate', 'heavy'] = 'moderate', test_case: str = None, **kwargs:dict):
        '''
        initialize the TrafficLoader class
        - param component: str, name of the component
        - param namespace: str, namespace of the component
        - param mode: Literal['light', 'moderate', 'heavy'], mode of the traffic
        - param test_case: int, test case number, if test_case is set, load test case and ignore component, namespace and mode
        - param kwargs: dict, other parameters
        '''
        super().__init__(**kwargs)
        
        if test_case:
            self.info(f"get test case, Load test case {test_case}")
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

    def _locust_traffic(self):
        '''
        Load traffic for locust
        '''
        args:dict = global_config['workload'][self.mode]
        # args: dict = load_yaml(os.path.join(config['data_path'], 'capacity', self.backend, self.namespace, f'{self.component}.yaml'))[self.mode]
        for key in ['users', 'spawn_rate']:
            if self.external_args.get(key, None):
                args[key] = self.external_args[key]
        args.update({
            'component': self.component,
            'namespace': self.namespace,
        })
        traffic = fill_content_in_yaml(global_config['traffic_loader']['template_path'], args)
        # print(traffic)
        return traffic

    def get_traffic(self):
        '''
        Get traffic for the specified component
        '''
        return self.__getattribute__(f'_{self.backend}_traffic')()

    def start(self):
        '''
        Load traffic for the specified component
        '''
        traffic = self.get_traffic()
        # print(traffic)
        subprocess.Popen(['kubectl', 'apply', '-f', '-'], stdin=subprocess.PIPE, text=True).communicate(traffic)
        self.info(f"Traffic load for {self.component} is set to {self.mode} mode")

    def stop(self):
        '''
        Remove traffic for the specified component
        '''
        subprocess.run(['kubectl', 'delete', '-f', global_config['traffic_loader']['template_path']], check=True)
        self.info(f"Traffic loaded for {self.component} is removed")