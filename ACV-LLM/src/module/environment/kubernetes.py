# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
import shutil
import subprocess
from .base import EnvironmentManager

class KubernetesEnvironmentManager(EnvironmentManager):
    def __init__(self, **kwargs) -> None:
        self.deployment = 'kubernetes'
        super().__init__(**kwargs)

    def setup(self, config_fpath: str = None):
        if os.path.exists(self.project_path):
            shutil.rmtree(self.project_path)
        
        temp_path = (
            (
                self.project_path[:-1]
                if self.project_path.endswith('/') 
                else self.project_path
            )
            + '-backup'
        )
        shutil.copytree(
            src=temp_path,
            dst=self.project_path
        )
        command = ['kubectl', 'apply', '-f', self.project_path]
        subprocess.run(command, check=True)
        time.sleep(10)
        if config_fpath:
            self.customize_resource(config_fpath)

    def teardown(self):
        command = ['kubectl', 'delete', 'namespace', self.namespace]
        subprocess.run(command, check=True)