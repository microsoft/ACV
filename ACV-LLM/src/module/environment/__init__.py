# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum
from .base import EnvironmentManager
from .kubernetes import KubernetesEnvironmentManager
from .helm import HelmEnvironmentManager

# Supported deployment types
deployment_types = ['kubernetes', 'helm']

class Environment(Enum):
    """
    Enumeration of supported deployment environments.

    Attributes:
    - Kubernetes: Represents a Kubernetes deployment environment.
    - Helm: Represents a Helm-based deployment environment.
    """
    Kubernetes = 'kubernetes'
    Helm = 'helm'

# Mapping from environment types to corresponding environment manager classes
enum2DeploymentType = {
    Environment.Kubernetes: KubernetesEnvironmentManager,
    Environment.Helm: HelmEnvironmentManager
}
