# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum

from .base import EnvironmentManager
from .kubernetes import KubernetesEnvironmentManager
from .helm import HelmEnvironmentManager

deployment_types = ['kubernetes', 'helm']

class Environment(Enum):
    Kubernetes = 'kubernetes'
    Helm = 'helm'

enum2DeploymentType = {
    Environment.Kubernetes: KubernetesEnvironmentManager,
    Environment.Helm: HelmEnvironmentManager
}