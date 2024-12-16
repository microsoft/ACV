# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Optional, Literal
from .base import (
    Chaos,
    Selector
)

class StressChaos(Chaos):
    """
    A StressChaos experiment simulates high CPU or memory load on a pod to test system stability under stress.

    Attributes:
    - kind (str): The kind of chaos experiment ('StressChaos').
    - stressors (dict): Configuration for the CPU and memory stressors.
    """

    class CPUStressor:
        """
        Represents a CPU stressor for the StressChaos experiment.

        Attributes:
        - workers (int): Number of threads applying CPU stress.
        - load (Optional[int]): Percentage of CPU load per worker (0-100).
        """

        def __init__(self, workers: int, load: Optional[int] = None):
            """
            Initialize a CPU stressor.

            Parameters:
            - workers (int): Number of threads applying CPU stress.
            - load (Optional[int], optional): Percentage of CPU load per worker (default: None).
            """
            self.workers: int = workers
            self.load: Optional[int] = load

    class MemoryStressor:
        """
        Represents a memory stressor for the StressChaos experiment.

        Attributes:
        - workers (Optional[int]): Number of threads applying memory stress.
        - size (Optional[str]): Total memory size for stress (e.g., '256MB', '50%').
        - time (Optional[str]): Time to reach the specified memory size (e.g., '1min').
        - oomScoreAdj (Optional[int]): Adjust the out-of-memory score for stress processes.
        """

        def __init__(
            self, 
            workers: Optional[int] = None, 
            size: Optional[str] = None, 
            time: Optional[str] = None, 
            oomScoreAdj: Optional[int] = None
        ):
            """
            Initialize a memory stressor.

            Parameters:
            - workers (Optional[int], optional): Number of threads applying memory stress (default: None).
            - size (Optional[str], optional): Total memory size for stress (default: None).
            - time (Optional[str], optional): Time to reach the memory size (default: None).
            - oomScoreAdj (Optional[int], optional): Adjust the out-of-memory score (default: None).
            """
            self.workers: Optional[int] = workers
            self.size: Optional[str] = size
            self.time: Optional[str] = time
            self.oomScoreAdj: Optional[int] = oomScoreAdj

    def __init__(
        self, 
        name: str, 
        namespace: str, 
        selector: Selector, 
        mode: Literal['one', 'all', 'fixed', 'fixed-percent', 'random-max-percent'] = 'all', 
        *args, 
        **kwargs
    ):
        """
        Initialize a StressChaos experiment.

        Parameters:
        - name (str): Name of the chaos experiment.
        - namespace (str): Namespace of the chaos experiment.
        - selector (Selector): Selector defining the target pods.
        - mode (str, optional): Mode of the chaos experiment (default: 'all').
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'StressChaos'
        self.stressors: dict = {}

        if 'cpu' in kwargs:
            self.stress_cpu(**kwargs['cpu'])
        if 'memory' in kwargs:
            self.stress_memory(**kwargs['memory'])

    def stress_cpu(self, workers: int, load: Optional[int] = None):
        """
        Add a CPU stressor to the chaos experiment.

        Parameters:
        - workers (int): Number of threads applying CPU stress.
        - load (Optional[int], optional): Percentage of CPU load per worker (0-100). Default is None.
        """
        cpu_stressor = self.CPUStressor(workers, load)
        self.stressors['cpu'] = cpu_stressor.__dict__

    def stress_memory(
        self, 
        workers: Optional[int] = None, 
        size: Optional[str] = None, 
        time: Optional[str] = None, 
        oomScoreAdj: Optional[int] = None
    ):
        """
        Add a memory stressor to the chaos experiment.

        Parameters:
        - workers (Optional[int], optional): Number of threads applying memory stress. Default is None.
        - size (Optional[str], optional): Total memory size for stress (e.g., '256MB', '50%'). Default is None.
        - time (Optional[str], optional): Time to reach the memory size (e.g., '1min'). Default is None.
        - oomScoreAdj (Optional[int], optional): Adjust the out-of-memory score for stress processes. Default is None.
        """
        memory_stressor = self.MemoryStressor(workers, size, time, oomScoreAdj)
        self.stressors['memory'] = memory_stressor.__dict__

    def construct(self):
        """
        Construct the chaos experiment.

        Returns:
        - dict: A dictionary representation of the chaos experiment.
        """
        self.spec['stressors'] = self.stressors
        return super().construct()
