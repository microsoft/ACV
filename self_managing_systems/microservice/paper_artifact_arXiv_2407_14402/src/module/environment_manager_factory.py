# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .environment import (
    Environment,
    EnvironmentManager,
    enum2DeploymentType,
)

class EnvironmentManagerFactory:
    """
    Factory class for creating instances of EnvironmentManager based on deployment type.
    """
    instance = None

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of the EnvironmentManagerFactory.

        Returns:
        - EnvironmentManagerFactory: The singleton instance of the factory.
        """
        if not cls.instance:
            cls.instance = EnvironmentManagerFactory()
        return cls.instance

    def get_environment(self, deployment_type: str, **kwargs) -> EnvironmentManager:
        """
        Get an instance of the appropriate EnvironmentManager based on the deployment type.

        Parameters:
        - deployment_type (str): The deployment type (e.g., 'kubernetes', 'helm').

        Returns:
        - EnvironmentManager: An instance of the corresponding EnvironmentManager.

        Raises:
        - ValueError: If the deployment type is invalid or unsupported.
        """
        try:
            e = Environment(deployment_type)
            return enum2DeploymentType[e](**kwargs)
        except KeyError:
            raise ValueError(f"Unsupported deployment type: {deployment_type}")
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .environment import (
    Environment,
    EnvironmentManager,
    enum2DeploymentType,
)

class EnvironmentManagerFactory:
    """
    Factory class for creating instances of EnvironmentManager based on deployment type.
    """
    instance = None

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of the EnvironmentManagerFactory.

        Returns:
        - EnvironmentManagerFactory: The singleton instance of the factory.
        """
        if not cls.instance:
            cls.instance = EnvironmentManagerFactory()
        return cls.instance

    def get_environment(self, deployment_type: str, **kwargs) -> EnvironmentManager:
        """
        Get an instance of the appropriate EnvironmentManager based on the deployment type.

        Parameters:
        - deployment_type (str): The deployment type (e.g., 'kubernetes', 'helm').

        Returns:
        - EnvironmentManager: An instance of the corresponding EnvironmentManager.

        Raises:
        - ValueError: If the deployment type is invalid or unsupported.
        """
        try:
            e = Environment(deployment_type)
            return enum2DeploymentType[e](**kwargs)
        except KeyError:
            raise ValueError(f"Unsupported deployment type: {deployment_type}")
