# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .base import *
from .stress_chaos import *
from .network_chaos import *
from .pod_chaos import *
from enum import Enum

# Supported chaos kinds in Chaos Engineering experiments
chaos_kinds = [
    'PodChaos', 'NetworkChaos', 'DNSChaos', 'HTTPChaos', 
    'StressChaos', 'IOChaos', 'TimeChaos', 'KernelChaos'
]

# Modes for selecting targets in Chaos experiments
modes = ['one', 'all', 'fixed', 'fixed-percent', 'random-max-percent']

class Experiment(Enum):
    """
    Enum representing different types of chaos experiments.

    Attributes:
    - StressChaos: Injects stress on CPU or memory resources.
    - PodFailure: Simulates a pod failure scenario.
    - PodKill: Terminates a specific pod in the Kubernetes cluster.
    - ContainerKill: Kills a container inside a pod.
    - Delay: Introduces network latency.
    - Loss: Simulates packet loss in the network.
    - Duplicate: Simulates packet duplication in the network.
    - Corrupt: Corrupts network packets.
    - Bandwidth: Restricts network bandwidth.
    """
    StressChaos = 'StressChaos'
    PodFailure = 'PodFailure'
    PodKill = 'PodKill'
    ContainerKill = 'ContainerKill'
    Delay = 'Delay'
    Loss = 'Loss'
    Duplicate = 'Duplicate'
    Corrupt = 'Corrupt'
    Bandwidth = 'Bandwidth'

# Mapping of experiment types to corresponding chaos classes
enum2Chaos = {
    Experiment.StressChaos: StressChaos,          # Maps StressChaos enum to StressChaos class
    Experiment.PodFailure: PodFailure,           # Maps PodFailure enum to PodFailure class
    Experiment.PodKill: PodKill,                 # Maps PodKill enum to PodKill class
    Experiment.ContainerKill: ContainerKill,     # Maps ContainerKill enum to ContainerKill class
    Experiment.Delay: Delay,                     # Maps Delay enum to Delay class
    Experiment.Loss: Loss,                       # Maps Loss enum to Loss class
    Experiment.Duplicate: Duplicate,             # Maps Duplicate enum to Duplicate class
    Experiment.Corrupt: Corrupt,                 # Maps Corrupt enum to Corrupt class
    Experiment.Bandwidth: Bandwidth              # Maps Bandwidth enum to Bandwidth class
}
