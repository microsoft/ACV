# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .chaos import (
    Experiment,
    Chaos,
    enum2Chaos
)

class ChaosFactory:
    """
    Factory class to create and manage Chaos experiment instances.
    """

    instance = None

    @classmethod
    def get_instance(cls):
        """
        Retrieve the singleton instance of the ChaosFactory.

        Returns:
        - ChaosFactory: The singleton instance of the factory.

        This method ensures that only one instance of ChaosFactory exists throughout the application.
        """
        if not cls.instance:
            cls.instance = ChaosFactory()
        return cls.instance

    def get_experiment(self, e: str, **kwargs) -> Chaos:
        """
        Create and retrieve an instance of a Chaos experiment.

        Parameters:
        - e (str): The type of Chaos experiment (must match the `Experiment` enumeration).
        - kwargs (dict): Additional parameters required for initializing the Chaos experiment.

        Returns:
        - Chaos: An instance of the specified Chaos experiment.

        Raises:
        - ValueError: If the provided experiment type does not match a valid `Experiment` enumeration.
        """
        e = Experiment(e)  # Convert string to Experiment enum
        if e not in enum2Chaos:
            raise ValueError(f"Invalid Chaos experiment type: {e}")
        return enum2Chaos[e](**kwargs)
