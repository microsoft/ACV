# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from agentscope.agents import ReActAgent
from agentscope.service import execute_python_code, execute_shell_command, ServiceToolkit

class ClusterManager(ReActAgent):
    """
    ClusterManager is a high-level agent that integrates reasoning and acting capabilities.
    It leverages the ReActAgent framework to handle tasks using a set of predefined tools.
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
        Initialize the ReActAgent with a name, model configuration, system prompt, and toolset.

        Parameters:
        - name (str): The name of the agent.
        - model_config_name (str): The configuration name for loading the model.
        - system_prompt (str): The system-level prompt used to guide the agent's behavior.
        - max_iters (int): The maximum number of reasoning-acting iterations. Default is 10.
        - verbose (bool): Whether to output detailed logs during reasoning and acting. Default is True.
        """
        
        # Initialize a toolkit for managing and executing services
        service_toolkit = ServiceToolkit()

        # Add Python code execution to the toolkit without using Docker isolation
        service_toolkit.add(execute_python_code, use_docker=False)

        # Add shell command execution to the toolkit
        service_toolkit.add(execute_shell_command)

        # Call the parent ReActAgent class initializer with the provided arguments and toolkit
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            sys_prompt=system_prompt,
            service_toolkit=service_toolkit,
            max_iters=max_iters,
            verbose=verbose,
        )
