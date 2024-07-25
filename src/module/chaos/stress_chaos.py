# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from typing import Optional, Literal
from .base import (
    Chaos,
    Selector
)

class StressChaos(Chaos):
    class CPUStressor:
        def __init__(self, workers: int, load: Optional[int] = None):
            self.workers: int = workers
            self.load: int

            if load:
                self.load = load

    class MemoryStressor:
        def __init__(self, workers: Optional[int], size: Optional[str], time: Optional[str], oomScoreAdj: Optional[int]):
            self.workers: int
            self.size: str
            self.time: str
            self.oomScoreAdj: int

            if workers:
                self.workers = workers
            if size:
                self.size = size
            if time:
                self.time = time
            if oomScoreAdj:
                self.oomScoreAdj = oomScoreAdj

    def __init__(self, name:str, namespace: str, selector: Selector, mode: Literal['one', 'all', 'fixed', 'fixed-percent', 'random-max-percent'] = 'all', *args, **kwargs):
        '''
        A StressChaos experiment simulates a high load on the CPU or memory of a pod.
        - param name: str, name of the chaos experiment
        - param namespace: str, namespace of the chaos experiment
        - selector: Selector, selector for the chaos experiment
        - mode: str, mode of the chaos experiment, e.g., 'all'
        '''
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'StressChaos'
        self.stressors: dict = dict()

        if 'cpu' in kwargs:
            self.stress_cpu(**kwargs['cpu'])
        if 'memory' in kwargs:
            self.stress_memory(**kwargs['memory'])

    def stress_cpu(self, workers: int, load: Optional[int] = None):
        '''
        Add a CPU stressor to the chaos experiment
        - param workers: int, Specifies the number of threads that apply CPU stress, e.g., 2
        - param load: int, Specifies the percentage of CPU occupied. 0 means that no additional CPU is added, and 100 refers to full load. The final sum of CPU load is workers * load, e.g., 50
        '''
        cpu_streesor = self.CPUStressor(workers, load)
        self.stressors['cpu'] = cpu_streesor.__dict__

    def stress_memory(self, workers: Optional[int] = None, size: Optional[str] = None, time: Optional[str] = None, oomScoreAdj: Optional[int] = None):
        '''
        Add a memory stressor to the chaos experiment
        - param workers: int, Specifies the number of threads that apply memory stress, e.g., 2
        - param size: str, Specifies the size of memory stress, e.g., '256MB','50%'
        - param time: str, Specifies the time to reach the memory size. The growth model is a linear model., e.g., '1min'
        - param oomScoreAdj: int, Specifies the oom_score_adj of the stress process, e.g., 1000
        '''
        memory_stressor = self.MemoryStressor(workers, size, time, oomScoreAdj)
        self.stressors['memory'] = memory_stressor.__dict__

    def construct(self):
        '''
        Construct the chaos experiment
        '''
        self.spec['stressors'] = self.stressors
        return super().construct()