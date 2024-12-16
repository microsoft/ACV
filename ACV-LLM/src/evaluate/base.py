# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from abc import ABC, abstractmethod
from ..module import Base

class Evaluator(ABC, Base):
    """
    Evaluator is an abstract base class for implementing test case evaluation 
    in the ACV Auto framework. It combines features of both `ABC` and `Base` 
    classes and requires subclasses to define the `evaluate` method.
    """

    def __init__(self, **kwargs: dict):
        """
        Initialize the Evaluator base class.
        
        Parameters:
        - kwargs (dict): Additional keyword arguments for initializing the base class.
        """
        super().__init__(**kwargs)

    @abstractmethod
    def evaluate(self, test_case: str, **kwargs: dict) -> bool:
        """
        Evaluate a given test case.

        This method must be implemented by any subclass of `Evaluator`.

        Parameters:
        - test_case (str): The test case to evaluate.
        - kwargs (dict): Additional keyword arguments to customize the evaluation process.

        Returns:
        - bool: True if the test case passes the evaluation criteria; False otherwise.

        Raises:
        - NotImplementedError: If the method is not implemented in the subclass.
        """
