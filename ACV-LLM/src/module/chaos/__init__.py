# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from .base import *
from .stress_chaos import *
from .network_chaos import *
from .pod_chaos import *
from enum import Enum

chaos_kinds = ['PodChaos', 'NetworkChaos', 'DNSChaos', 'HTTPChaos', 'StressChaos', 'IOChaos', 'TimeChaos', 'KernelChaos']
modes = ['one', 'all', 'fixed', 'fixed-percent', 'random-max-percent']

class Experiment(Enum):
    StressChaos = 'StressChaos'
    PodFailure = 'PodFailure'
    PodKill = 'PodKill'
    ContainerKill = 'ContainerKill'
    Delay = 'Delay'
    Loss = 'Loss'
    Duplicate = 'Duplicate'
    Corrupt = 'Corrupt'
    Bandwidth = 'Bandwidth'

enum2Chaos = {
    Experiment.StressChaos: StressChaos,
    Experiment.PodFailure: PodFailure,
    Experiment.PodKill: PodKill,
    Experiment.ContainerKill: ContainerKill,
    Experiment.Delay: Delay,
    Experiment.Loss: Loss,
    Experiment.Duplicate: Duplicate,
    Experiment.Corrupt: Corrupt,
    Experiment.Bandwidth: Bandwidth
}