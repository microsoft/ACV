# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from agentscope.agents import ReActAgent
from agentscope.service import execute_python_code, execute_shell_command, ServiceToolkit

from ..module import load_config, Prompter

from .utils import (
    load_service_maintainer_config,
)

# Load global configuration settings
global_config = load_config()

class ServiceMaintainer(ReActAgent):
    """
    ServiceMaintainer is a low-level agent responsible for executing specific tasks 
    using reasoning-acting loops. It leverages the ReActAgent framework and integrates
    service-specific tools for task execution.
    """

    def __init__(
        self, 
        name: str,
        model_config_name: str,
        system_prompt: str,
        max_iters: int = 10,
        verbose: bool = True,
    ) -> None:
        """
        Initialize the ServiceMaintainer agent with a name, model configuration, 
        system prompt, and tools.

        Parameters:
        - name (str): The name of the agent.
        - model_config_name (str): The name of the model configuration for loading the model.
        - system_prompt (str): The system-level prompt to guide the agent's behavior.
        - max_iters (int): The maximum number of reasoning-acting iterations. Default is 10.
        - verbose (bool): Whether to print detailed logs during reasoning and acting. Default is True.
        """
        # Initialize a service toolkit for managing task execution
        service_toolkit = ServiceToolkit()

        # Add Python code execution capability to the toolkit without Docker isolation
        service_toolkit.add(execute_python_code, use_docker=False)

        # Add shell command execution capability to the toolkit
        service_toolkit.add(execute_shell_command)

        # Call the parent ReActAgent initializer with the provided arguments and toolkit
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            sys_prompt=system_prompt,
            service_toolkit=service_toolkit,
            max_iters=max_iters,
            verbose=verbose,
        )

    @staticmethod
    def _init_from_config(service_name: str, model_config_name: str) -> "ServiceMaintainer":
        """
        Static method to initialize a ServiceMaintainer agent from a configuration file.

        Parameters:
        - service_name (str): The name of the service to be maintained.
        - model_config_name (str): The name of the model configuration for the agent.

        Returns:
        - ServiceMaintainer: An initialized ServiceMaintainer agent.
        """
        # Load service-specific configuration
        service_maintainer_config = load_service_maintainer_config(global_config['project']['name'], service_name)

        # Initialize a Prompter to generate the system prompt for the agent
        prompter = Prompter()
        prompter.load_prompt_template(global_config['agent']['service_prompt_template_path'])
        prompter.fill_system_message(service_maintainer_config)

        # Create and return the ServiceMaintainer agent
        agent = ServiceMaintainer(
            name=service_name,
            model_config_name=model_config_name,
            system_prompt=prompter.system_message,
        )
        return agent

    def __repr__(self) -> str:
        """
        Representation of the ServiceMaintainer instance.

        Returns:
        - str: A string representation of the agent, including its name, description, and backend model.
        """
        return (
            f"ServiceMaintainer({self.name})\n "
            f"Description: {self.description}\n backend: {self.model}"
        )
