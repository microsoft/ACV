# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import Optional, Literal

class Selector:
    def __init__(self, namespaces: Optional[list[str]] = None, labelSelectors: Optional[dict[str, str]] = None, pods: Optional[dict[str, list[str]]] = None, **kwargs):
        '''
        Initialize selector in chaos-mesh experiment
        - param namespaces: list[str], list of namespaces, e.g., ['default']
        - param labelSelectors: dict[str, str], label selectors, e.g., {'name': 'catalogue'}
        - param pods: dict[str, list[str]], pods, e.g., ['catalogue-59bf4f7bc7-b6mz7']
        '''
        self.namespaces: list[str]
        self.labelSelectors: dict[str, str]
        self.pods: dict[str, list[str]]

        if namespaces:
            self.namespaces = namespaces
        if labelSelectors:
            self.labelSelectors = labelSelectors
        if pods:
            self.pods = pods

class Chaos:
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Base class for all chaos experiments
        - param name: str, name of the chaos experiment
        - param namespace: str, namespace of the chaos experiment
        - selector: Selector, selector for the chaos experiment
        - mode: str, mode of the chaos experiment, e.g., 'all'
        '''
        self.name: str = name
        self.namespace: str = namespace
        self.selector: Selector = selector
        self.kind: Literal['PodChaos', 'NetworkChaos', 'DNSChaos', 'HTTPChaos', 'StressChaos', 'IOChaos', 'TimeChaos', 'KernelChaos']
        self.apiVersion: str = 'chaos-mesh.org/v1alpha1'
        self.metadata: dict[str, str] = dict()
        self.spec: dict = dict()
        self.mode: Literal['one', 'all', 'fixed', 'fixed-percent', 'random-max-percent']
        self.value: Optional[str] = None

        self.metadata['name'] = name
        self.metadata['namespace'] = namespace
        self.mode = mode

    def construct(self):
        '''
        Construct the chaos experiment
        '''
        self.spec['selector'] = self.selector.__dict__
        self.spec['mode'] = self.mode
        if self.value:
            self.spec['value'] = self.value
        return {
            'kind': self.kind,
            'apiVersion': self.apiVersion,
            'metadata': self.metadata,
            'spec': self.spec
        }