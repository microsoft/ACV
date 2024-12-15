from abc import ABC, abstractmethod
from ..module import Base


class Evaluator(ABC, Base):
    """Base class for ACV Auto evaluator."""
    def __init__(self, **kwargs: dict):
        super().__init__(**kwargs)

    @abstractmethod
    def evaluate(self, test_case: str,**kwargs: dict) -> bool:
        """
        Evaluate the test case.

        Args:
            test_case (str): The test case to evaluate.
            **kwargs (dict): The keyword arguments to pass to the test case.

        Raises:
            NotImplementedError: If the test case is not implemented.

        Returns:
            bool: The evaluation result
        """