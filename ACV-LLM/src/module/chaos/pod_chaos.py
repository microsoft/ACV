# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal, Optional
from .base import (
    Chaos,
    Selector
)

class PodChaos(Chaos):
    """
    Base class for PodChaos experiments, which simulate pod-related faults such as pod failure,
    pod killing, or container killing.

    Attributes:
    - action (Literal): The type of pod chaos action ('pod-kill', 'container-kill', 'pod-failure').
    - duration (str): The duration of the fault (if applicable).
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        selector: Selector,
        mode: str = 'all',
        *args,
        **kwargs
    ):
        """
        Initialize a PodChaos experiment.

        Parameters:
        - name (str): The name of the chaos experiment.
        - namespace (str): The namespace of the chaos experiment.
        - selector (Selector): Selector to define the target pods for the chaos experiment.
        - mode (str, optional): The mode of target selection (default: 'all').
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.kind = 'PodChaos'
        self.action: Literal['pod-kill', 'container-kill', 'pod-failure'] = ''
        self.duration: Optional[str] = None

    def construct(self):
        """
        Construct the PodChaos experiment specification.

        Returns:
        - dict: A dictionary representation of the chaos experiment.
        """
        self.spec['action'] = self.action
        return super().construct()


class PodFailure(PodChaos):
    """
    Class to simulate pod failure faults.

    Attributes:
    - action (Literal): Action type is set to 'pod-failure'.
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        selector: Selector,
        mode: str = 'all',
        *args,
        **kwargs
    ):
        """
        Initialize a PodFailure experiment.

        Parameters:
        - name (str): The name of the chaos experiment.
        - namespace (str): The namespace of the chaos experiment.
        - selector (Selector): Selector to define the target pods for the chaos experiment.
        - mode (str, optional): The mode of target selection (default: 'all').
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'pod-failure'


class PodKill(PodChaos):
    """
    Class to simulate pod kill faults.

    Attributes:
    - action (Literal): Action type is set to 'pod-kill'.
    - gracePeriod (str): The duration to wait before killing the pod.
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        selector: Selector,
        mode: str = 'all',
        *args,
        **kwargs
    ):
        """
        Initialize a PodKill experiment.

        Parameters:
        - name (str): The name of the chaos experiment.
        - namespace (str): The namespace of the chaos experiment.
        - selector (Selector): Selector to define the target pods for the chaos experiment.
        - mode (str, optional): The mode of target selection (default: 'all').
        - gracePeriod (str, optional): The duration before deleting the pod (e.g., '10s').
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'pod-kill'
        self.gracePeriod: Optional[str] = None

        if 'gracePeriod' in kwargs:
            self.spec['gracePeriod'] = kwargs['gracePeriod']


class ContainerKill(PodChaos):
    """
    Class to simulate container kill faults.

    Attributes:
    - action (Literal): Action type is set to 'container-kill'.
    - containerNames (list[str]): The names of the containers to target for the chaos experiment.
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        selector: Selector,
        mode: str = 'all',
        *args,
        **kwargs
    ):
        """
        Initialize a ContainerKill experiment.

        Parameters:
        - name (str): The name of the chaos experiment.
        - namespace (str): The namespace of the chaos experiment.
        - selector (Selector): Selector to define the target pods for the chaos experiment.
        - mode (str, optional): The mode of target selection (default: 'all').
        - containerNames (list[str], optional): The names of the target containers (e.g., ['nginx']).
        """
        super().__init__(name=name, namespace=namespace, selector=selector, mode=mode, *args, **kwargs)
        self.action = 'container-kill'
        self.containerNames: Optional[list[str]] = None

        if 'containerNames' in kwargs:
            self.spec['containerNames'] = kwargs['containerNames']
