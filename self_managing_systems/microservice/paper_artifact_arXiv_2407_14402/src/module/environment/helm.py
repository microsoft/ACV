# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import subprocess
from .base import EnvironmentManager

class HelmEnvironmentManager(EnvironmentManager):
    """
    Manages the deployment and teardown of environments using Helm.

    Attributes:
    - deployment (str): Deployment type set to 'helm'.
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the HelmEnvironmentManager.

        Parameters:
        - kwargs: Additional keyword arguments passed to the base EnvironmentManager.
        """
        self.deployment = 'helm'
        super().__init__(**kwargs)

    def setup(self, config_fpath: str = None):
        """
        Set up the Helm environment.

        Parameters:
        - config_fpath (str, optional): Path to the configuration file for customizing resources (default: None).

        Steps:
        1. Create the Kubernetes namespace for the project.
        2. Install the Helm chart for the project.
        3. Wait for the installation to stabilize.
        4. Customize resources using the provided configuration file.
        """
        # Create namespace
        command = ['kubectl', 'create', 'namespace', self.namespace]
        subprocess.run(command, check=True)

        # Install Helm chart
        command = [
            'helm', 'install', self.project, self.project_path,
            '--namespace', self.namespace
        ]
        subprocess.run(command, check=True)

        # Wait for the deployment to stabilize
        time.sleep(10)

        # Customize resources if a configuration file is provided
        if config_fpath:
            self.customize_resource(config_fpath)

    def teardown(self):
        """
        Tear down the Helm environment.

        Steps:
        1. Uninstall the Helm chart.
        2. Delete the Kubernetes namespace for the project.
        """
        # Uninstall Helm chart
        command = [
            'helm', 'uninstall', self.project,
            '--namespace', self.namespace
        ]
        subprocess.run(command, check=True)

        # Delete namespace
        command = ['kubectl', 'delete', 'namespace', self.namespace]
        subprocess.run(command, check=True)
