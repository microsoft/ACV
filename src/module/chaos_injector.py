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
    def __init__(self, **kwargs) -> None:
        '''
        Initialize chaos injector from base class
        '''
        super().__init__(**kwargs)
        self._chaos: Chaos = None
        self.context: dict = None
        self.status: Literal['stopped', 'paused', 'running'] = 'stopped'
        self.fpath = None

        if 'chaos' in kwargs:
            self._chaos = kwargs['chaos']

    @property
    def chaos(self):
        return self._chaos

    def start_experiment(self):
        '''
        Start the chaos experiment
        '''
        if self._chaos is not None and self.status == 'running':
            self.warning('Experiment already running, please stop it first.')
            return
        
        self.fpath = os.path.join(global_config['chaos_path'], 'experiments', f"{self._chaos.name}.yaml")
        yaml.safe_dump(self._chaos.construct(), open(self.fpath, 'w'), default_flow_style=False)
        
        self.info('Starting experiment')
        if self.context and 'annotations' in self.context['metadata']:
            self.context['metadata']['annotations']['experiment.chaos-mesh.org/pause'] = 'false'
            yaml.safe_dump(self._chaos.construct(), open(self.fpath, 'w'), default_flow_style=False)

        self.context = self._chaos.construct()
        result = subprocess.run(['kubectl', 'apply', '-f', self.fpath])
        if result.returncode != 0:
            self.error('Failed to start experiment.')
            self._chaos = None
            self.context = None
            return
        
        self.status = 'running'

    def delete_experiment(self):
        '''
        Stop the chaos experiment
        '''
        if self.status != 'running':
            self.warning('No experiment running.')
            return
        
        self.info('Stopping experiment')
        result = subprocess.run(['kubectl', 'delete', '-f', self.fpath])
        if result.returncode != 0:
            self.error('Failed to stop experiment.')
            return
        
        self._chaos = None
        self.context = None
        self.status = 'stopped'
    
    def pause_experiment(self):
        '''
        Pause the chaos experiment
        '''
        if self.status != 'running':
            self.warning('No experiment running.')
            return

        if self.context and 'annotations' not in self.context['metadata']:
            self.context['metadata']['annotations'] = dict()
        self.context['metadata']['annotations']['experiment.chaos-mesh.org/pause'] = 'true'
        yaml.safe_dump(self.context, open(self.fpath, 'w'), default_flow_style=False)
        
        self.info('Pausing experiment')
        result = subprocess.run(['kubectl', 'apply', '-f', self.fpath])
        if result.returncode != 0:
            self.error('Failed to pause experiment.')
            return
        
        self.status = 'paused'