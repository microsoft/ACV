# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import yaml
import subprocess
from typing import Literal
from .base import Base
from .chaos import Chaos
from .utils import load_config

global_config = load_config()

class ChaosInjector(Base):
    """
    The `ChaosInjector` class manages the lifecycle of chaos experiments, including starting, pausing, 
    and stopping experiments using Chaos Mesh in a Kubernetes environment.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the ChaosInjector with optional chaos and configuration settings.

        Parameters:
        - chaos (Chaos, optional): The chaos experiment to manage.
        - kwargs (dict): Additional parameters passed to the base class.
        """
        super().__init__(**kwargs)
        self._chaos: Chaos = kwargs.get('chaos', None)
        self.context: dict = None
        self.status: Literal['stopped', 'paused', 'running'] = 'stopped'
        self.fpath = None

    @property
    def chaos(self) -> Chaos:
        """
        Get the current chaos experiment.

        Returns:
        - Chaos: The current chaos experiment object.
        """
        return self._chaos

    def start_experiment(self):
        """
        Start the chaos experiment.

        This method creates the YAML file for the chaos experiment and applies it using `kubectl`.
        If an experiment is already running, it will log a warning.
        """
        if self._chaos is not None and self.status == 'running':
            self.warning('Experiment already running, please stop it first.')
            return

        self.fpath = os.path.join(global_config['chaos_path'], 'experiments', f"{self._chaos.name}.yaml")
        yaml.safe_dump(self._chaos.construct(), open(self.fpath, 'w'), default_flow_style=False)

        self.info('Starting experiment...')
        if self.context and 'annotations' in self.context.get('metadata', {}):
            self.context['metadata']['annotations']['experiment.chaos-mesh.org/pause'] = 'false'
            yaml.safe_dump(self._chaos.construct(), open(self.fpath, 'w'), default_flow_style=False)

        self.context = self._chaos.construct()
        result = subprocess.run(['kubectl', 'apply', '-f', self.fpath])
        print(f'The chaos experiment is running with the following configuration: {self.fpath}')
        if result.returncode != 0:
            self.error('Failed to start experiment.')
            self._chaos = None
            self.context = None
            return

        self.status = 'running'

    def delete_experiment(self):
        """
        Stop the chaos experiment.

        This method deletes the chaos experiment using `kubectl`. If no experiment is running, it logs a warning.
        """
        if self.status != 'running':
            self.warning('No experiment running.')
            return

        self.info('Stopping experiment...')
        result = subprocess.run(['kubectl', 'delete', '-f', self.fpath])
        if result.returncode != 0:
            self.error('Failed to stop experiment.')
            return

        self._chaos = None
        self.context = None
        self.status = 'stopped'

    def pause_experiment(self):
        """
        Pause the chaos experiment.

        This method modifies the experiment's annotations to pause it using `kubectl`.
        If no experiment is running, it logs a warning.
        """
        if self.status != 'running':
            self.warning('No experiment running.')
            return

        if self.context and 'annotations' not in self.context.get('metadata', {}):
            self.context['metadata']['annotations'] = {}
        self.context['metadata']['annotations']['experiment.chaos-mesh.org/pause'] = 'true'
        yaml.safe_dump(self.context, open(self.fpath, 'w'), default_flow_style=False)

        self.info('Pausing experiment...')
        result = subprocess.run(['kubectl', 'apply', '-f', self.fpath])
        if result.returncode != 0:
            self.error('Failed to pause experiment.')
            return

        self.status = 'paused'
