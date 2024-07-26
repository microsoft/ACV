# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from .chaos import (
    Experiment,
    Chaos,
    enum2Chaos
)

class ChaosFactory:
    instance = None
    @classmethod
    def get_instance(cls):
        '''
        Get instance of ChaosFactory
        '''
        if not cls.instance:
            cls.instance = ChaosFactory()
        return cls.instance

    def get_experiment(self, e: str, **kwargs) -> Chaos:
        '''
        Get instance of chaos experiment
        - param e: Experiment, chaos experiment type
        '''
        e = Experiment(e)
        return enum2Chaos[e](**kwargs)