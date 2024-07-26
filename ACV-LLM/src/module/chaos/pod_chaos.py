# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import Literal
from .base import (
    Chaos,
    Selector
)

class PodChaos(Chaos):
    def __init__(self, name:str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        A PodChaos experiment simulates a pod failure by killing the pod or container.
        - param name: str, name of the chaos experiment
        - param namespace: str, namespace of the chaos experiment
        - selector: Selector, selector for the chaos experiment
        - mode: str, mode of the chaos experiment, e.g., 'all'
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'PodChaos'
        self.action: Literal['pod-kill', 'container-kill', 'pod-failure']
        self.duration: str

    def construct(self):
        '''
        Construct the chaos experiment
        '''
        self.spec['action'] = self.action
        return super().construct()

class PodFailure(PodChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to pod-failure means simulating pod failure fault.
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'pod-failure'

class PodKill(PodChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to pod-kill means simulating pod kill fault.
        - param gracePeriod: str, When you configure action to pod-kill, this configuration is mandatory to specify the duration before deleting Pod, e.g., '10s'
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'pod-kill'
        self.gracePeriod: str

        if 'gracePeriod' in kwargs:
            self.spec['gracePeriod'] = kwargs['gracePeriod']

class ContainerKill(PodChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to container-kill means simulating container kill fault.
        - param containerNames: list[str], When you configure action to container-kill, this configuration is mandatory to specify the target container name for injecting faults, e.g., ['nginx']
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'container-kill'
        self.containerNames: list[str]

        if 'containerNames' in kwargs:
            self.spec['containerNames'] = kwargs['containerNames']
