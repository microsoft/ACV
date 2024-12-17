# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal
from .base import (
    Chaos,
    Selector
)

class NetworkChaos(Chaos):
    """
    Base class for all network-related chaos experiments in Chaos Mesh.

    Attributes:
    - action (Literal): The type of network fault (e.g., 'Partition', 'Loss', 'Delay').
    - direction (Literal): The direction of the network fault ('to', 'from', or 'both').
    - target (dict[str, str]): Target specification for the fault.
    - externalTargets (list[str]): External targets for the fault.
    - device (str): The network interface to apply the fault.
    - action_spec (dict): Specific configurations for the chosen action.
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
        Initialize a network chaos experiment.

        Parameters:
        - name (str): The name of the chaos experiment.
        - namespace (str): The namespace of the experiment.
        - selector (Selector): Selector for the target resources.
        - mode (str, optional): The mode of target selection (default: 'all').
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'NetworkChaos'
        self.action: Literal['Partition', 'Loss', 'Delay', 'Duplicate', 'Corrupt', 'Bandwidth']
        self.direction: Literal['to', 'from', 'both']
        self.target: dict[str, str] = {}
        self.externalTargets: list[str] = []
        self.device: str = ''
        self.action_spec: dict = {}

        for arg in ['direction', 'target', 'externalTargets', 'device']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

    def construct(self):
        """
        Construct the chaos experiment specification.

        Returns:
        - dict: A dictionary representation of the chaos experiment.
        """
        self.spec['action'] = self.action
        self.spec[self.action] = self.action_spec
        return super().construct()


class Delay(NetworkChaos):
    """
    Simulate network delay faults.
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
        Initialize a delay network chaos experiment.

        Parameters:
        - latency (str): The network latency (e.g., '10ms').
        - jitter (str): The range of the network latency (e.g., '5ms').
        - correlation (str): Correlation between current and previous latency values (range: [0, 100]).
        - reorder (dict): Configuration for packet reordering.
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.latency: str = ''
        self.jitter: str = ''
        self.correlation: str = ''
        self.reorder: dict = {}
        self.action = 'delay'

        for arg in ['latency', 'jitter', 'correlation', 'reorder']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]


class Loss(NetworkChaos):
    """
    Simulate packet loss faults.
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
        Initialize a packet loss network chaos experiment.

        Parameters:
        - loss (str): The probability of packet loss (range: [0, 100]).
        - correlation (str): Correlation between current and previous packet loss probabilities (range: [0, 100]).
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.loss: str = ''
        self.correlation: str = ''
        self.action = 'loss'

        for arg in ['loss', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]


class Duplicate(NetworkChaos):
    """
    Simulate packet duplication faults.
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
        Initialize a packet duplication network chaos experiment.

        Parameters:
        - duplicate (str): The probability of packet duplication (range: [0, 100]).
        - correlation (str): Correlation between current and previous packet duplication probabilities (range: [0, 100]).
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.duplicate: str = ''
        self.correlation: str = ''
        self.action = 'duplicate'

        for arg in ['duplicate', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]


class Corrupt(NetworkChaos):
    """
    Simulate packet corruption faults.
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
        Initialize a packet corruption network chaos experiment.

        Parameters:
        - corrupt (str): The probability of packet corruption (range: [0, 100]).
        - correlation (str): Correlation between current and previous packet corruption probabilities (range: [0, 100]).
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.corrupt: str = ''
        self.correlation: str = ''
        self.action = 'corrupt'

        for arg in ['corrupt', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]


class Bandwidth(NetworkChaos):
    """
    Simulate bandwidth limitation faults.
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
        Initialize a bandwidth limitation network chaos experiment.

        Parameters:
        - rate (str): The rate of bandwidth limitation (e.g., '1mbps').
        - limit (int): The maximum number of bytes in the queue (e.g., 1000).
        - buffer (int): The maximum number of bytes sent instantaneously (e.g., 1024).
        - peakrate (int): The maximum consumption of the bucket (usually not set).
        - minburst (int): The size of the peakrate bucket (usually not set).
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.rate: str = ''
        self.limit: int = 0
        self.buffer: int = 0
        self.peakrate: int = 0
        self.minburst: int = 0
        self.action = 'bandwidth'

        for arg in ['rate', 'limit', 'buffer', 'peakrate', 'minburst']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]
