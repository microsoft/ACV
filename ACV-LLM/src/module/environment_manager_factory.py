# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .environment import (
    Environment,
    EnvironmentManager,
    enum2DeploymentType,
)

class EnvironmentManagerFactory:
    instance = None
    @classmethod
    def get_instance(cls):
        '''
        Get instance of EnvironmentManagerFactory
        '''
        if not cls.instance:
            cls.instance = EnvironmentManagerFactory()
        return cls.instance

    def get_environment(self, deployment_type: str, **kwargs) -> EnvironmentManager:
        '''
        Get instance of environment manager
        - param deployment_type: str, deployment type
        '''
        e = Environment(deployment_type)
        return enum2DeploymentType[e](**kwargs)