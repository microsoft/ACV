# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import subprocess
from .base import EnvironmentManager

class HelmEnvironmentManager(EnvironmentManager):
    def __init__(self, **kwargs) -> None:
        self.deployment = 'helm'
        super().__init__(**kwargs)

    def setup(self, config_fpath: str = None):
        command = ['kubectl', 'create', 'namespace', self.namespace]
        subprocess.run(command)

        command = [
            'helm', 'install', self.project, self.project_path, 
            '--namespace', self.namespace
        ]
        subprocess.run(command)
        time.sleep(10)
        self.customize_resource(config_fpath)

    def teardown(self):
        command = [
            'helm', 'uninstall', self.project,
            '--namespace', self.namespace
        ]
        subprocess.run(command)
        
        command = ['kubectl', 'delete', 'namespace', self.namespace]
        subprocess.run(command)