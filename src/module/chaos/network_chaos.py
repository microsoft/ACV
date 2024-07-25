# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import Literal
from .base import (
    Chaos,
    Selector
)

class NetworkChaos(Chaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        NetworkChaos is a fault type in Chaos Mesh. By creating a NetworkChaos experiment, you can simulate a network fault scenario for a cluster.
        Currently, NetworkChaos supports the following fault types:
        - Partition: network disconnection and partition.
        - Net Emulation: poor network conditions, such as high delays, high packet loss rate, packet reordering, and so on.
        - Bandwidth: limit the communication bandwidth between nodes.
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'NetworkChaos'
        self.action: Literal['Partition', 'Loss', 'Delay', 'Duplicate', 'Corrupt', 'Bandwidth']
        self.direction: Literal['to', 'from', 'both']
        self.target: dict[str, str]
        self.externalTargets: list[str]
        self.device: str
        self.action_spec: dict = dict()
        for arg in ['direction', 'target', 'externalTargets', 'device']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

    def construct(self):
        '''
        Construct the chaos experiment
        '''
        self.spec['action'] = self.action
        self.spec[self.action] = self.action_spec

        return super().construct()

class Delay(NetworkChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to delay means simulating network delay fault.
        - param latency: str, Indicates the network latency, e.g., '10ms'
        - param jitter: str, range of the network latency, e.g., '5ms'
        - param correlation: str, the correlation between the current latency and the previous one. Range of value: [0, 100]
        - param reorder: Reorder, reorder the network packets
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.latency: str
        self.jitter: str
        self.correlation: str
        self.reorder: dict
        self.action = 'delay'

        for arg in ['latency', 'jitter', 'correlation', 'reorder']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

class Loss(NetworkChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to loss means simulating packet loss fault. You can also configure the following parameters.
        - param loss: str, Indicates the probability of packet loss. Range of value: [0, 100]
        - param correlation: str, Indicates the correlation between the probability of current packet loss and the previous time's packet loss. Range of value: [0, 100]
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.loss: str
        self.correlation: str
        self.action = 'loss'

        for arg in ['loss', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

class Duplicate(NetworkChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Set action to duplicate, meaning simulating package duplication.
        - param duplicate: str, Indicates the probability of packet duplicating. Range of value: [0, 100]
        - param correlation: str, Indicates the correlation between the probability of current packet duplicating and the previous time's packet duplicating. Range of value: [0, 100]
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.duplicate: str
        self.correlation: str
        self.action = 'duplicate'

        for arg in ['duplicate', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

class Corrupt(NetworkChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to corrupt means simulating package corruption fault.
        - param corrupt: str, Indicates the probability of packet corruption. Range of value: [0, 100]
        - param correlation: str, Indicates the correlation between the probability of current packet corruption and the previous time's packet corruption. Range of value: [0, 100]
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.corrupt: str
        self.correlation: str
        self.action = 'corrupt'

        for arg in ['corrupt', 'correlation']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]

class Bandwidth(NetworkChaos):
    def __init__(self, name: str, namespace: str, selector: Selector, mode: str = 'all', *args, **kwargs):
        '''
        Setting action to bandwidth means simulating bandwidth limit fault.
        - param rate: str, Indicates the rate of bandwidth limit, e.g., '1mbps'
        - param limit: int, Indicates the number of bytes waiting in queue, e.g., 1000
        - param buffer: int, Indicates the maximum number of bytes that can be sent instantaneously, e.g., 1024
        - param peakrate: int, Indicates the maximum consumption of bucket (usually not set), e.g., 1
        - param minburst: int, Indicates the size of peakrate bucket (usually not set), e.g., 1000
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.rate: str
        self.limit: str
        self.buffer: int
        self.peakrate: int
        self.minburst: int
        self.action = 'bandwidth'

        for arg in ['rate', 'limit', 'buffer', 'peakrate', 'minburst']:
            if arg in kwargs:
                self.action_spec[arg] = kwargs[arg]
