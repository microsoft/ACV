# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal

class Selector:
    """
    Represents the target resources for a chaos-mesh experiment.
    
    Attributes:
    - namespaces (list[str]): List of namespaces to target, e.g., ['default'].
    - labelSelectors (dict[str, str]): Label selectors to filter resources, e.g., {'name': 'catalogue'}.
    - pods (dict[str, list[str]]): Specific pods to target, e.g., {'default': ['catalogue-59bf4f7bc7-b6mz7']}.
    """

    def __init__(
        self, 
        namespaces: Optional[list[str]] = None, 
        labelSelectors: Optional[dict[str, str]] = None, 
        pods: Optional[dict[str, list[str]]] = None, 
        **kwargs
    ):
        """
        Initialize the selector for a chaos-mesh experiment.

        Parameters:
        - namespaces (list[str], optional): Namespaces to include in the experiment.
        - labelSelectors (dict[str, str], optional): Label-based selectors to filter resources.
        - pods (dict[str, list[str]], optional): Specific pods to target for the experiment.
        """
        self.namespaces: Optional[list[str]] = namespaces or []
        self.labelSelectors: Optional[dict[str, str]] = labelSelectors or {}
        self.pods: Optional[dict[str, list[str]]] = pods or {}

class Chaos:
    """
    Base class for all chaos-mesh experiments.

    Attributes:
    - name (str): The name of the chaos experiment.
    - namespace (str): The namespace in which the experiment runs.
    - selector (Selector): A selector object defining the target resources.
    - kind (Literal): The kind of chaos experiment (e.g., 'PodChaos', 'NetworkChaos').
    - apiVersion (str): API version for the chaos-mesh resource.
    - metadata (dict): Metadata containing experiment details such as name and namespace.
    - spec (dict): Specification for the chaos experiment.
    - mode (Literal): Mode for selecting targets ('one', 'all', 'fixed', etc.).
    - value (Optional[str]): Additional value for the experiment configuration (e.g., percentage).
    """

    def __init__(
        self, 
        name: str, 
        namespace: str, 
        selector: Selector, 
        mode: str = 'all', 
        *args, 
        **kwargs
    ):
        """
        Initialize the base chaos experiment.

        Parameters:
        - name (str): Name of the chaos experiment.
        - namespace (str): Namespace of the chaos experiment.
        - selector (Selector): Selector defining the target resources.
        - mode (str, optional): Mode of the experiment (default: 'all').
        """
        self.name: str = name
        self.namespace: str = namespace
        self.selector: Selector = selector
        self.kind: Literal[
            'PodChaos', 'NetworkChaos', 'DNSChaos', 'HTTPChaos', 
            'StressChaos', 'IOChaos', 'TimeChaos', 'KernelChaos'
        ]
        self.apiVersion: str = 'chaos-mesh.org/v1alpha1'
        self.metadata: dict[str, str] = {
            'name': name,
            'namespace': namespace
        }
        self.spec: dict = {}
        self.mode: Literal[
            'one', 'all', 'fixed', 'fixed-percent', 'random-max-percent'
        ] = mode
        self.value: Optional[str] = None

    def construct(self) -> dict:
        """
        Construct the chaos experiment configuration.

        Returns:
        - dict: A dictionary representation of the chaos experiment.
        """
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
