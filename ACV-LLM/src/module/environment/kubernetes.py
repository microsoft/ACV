# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
import shutil
import subprocess
from .base import EnvironmentManager

class KubernetesEnvironmentManager(EnvironmentManager):
    """
    Manages the deployment and teardown of environments using Kubernetes manifests.

    Attributes:
    - deployment (str): Deployment type set to 'kubernetes'.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the KubernetesEnvironmentManager.

        Parameters:
        - kwargs: Additional keyword arguments passed to the base EnvironmentManager.
        """
        self.deployment = 'kubernetes'
        super().__init__(**kwargs)

    def setup(self, config_fpath: str = None):
        """
        Set up the Kubernetes environment.

        Parameters:
        - config_fpath (str, optional): Path to the configuration file for customizing resources (default: None).

        Steps:
        1. Remove the existing project directory if it exists.
        2. Restore the project directory from a backup.
        3. Apply the Kubernetes manifests from the project path.
        4. Wait for the deployment to stabilize.
        5. Customize resources using the provided configuration file (if any).
        """
        # Remove existing project path if it exists
        if os.path.exists(self.project_path):
            shutil.rmtree(self.project_path)

        # Restore project path from backup
        temp_path = (
            self.project_path.rstrip('/') + '-backup'
        )
        shutil.copytree(
            src=temp_path,
            dst=self.project_path
        )

        # Apply Kubernetes manifests
        command = ['kubectl', 'apply', '-f', self.project_path]
        subprocess.run(command, check=True)

        # Wait for the deployment to stabilize
        time.sleep(10)

        # Customize resources if a configuration file is provided
        if config_fpath:
            self.customize_resource(config_fpath)

    def teardown(self):
        """
        Tear down the Kubernetes environment.

        Steps:
        1. Delete the Kubernetes namespace for the project.
        """
        # Delete namespace
        command = ['kubectl', 'delete', 'namespace', self.namespace]
        subprocess.run(command, check=True)
