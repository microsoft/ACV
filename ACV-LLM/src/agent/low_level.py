from agentscope.agents import ReActAgent
from agentscope.service import execute_python_code, execute_shell_command, ServiceToolkit

from ..module import load_config, Prompter

from .utils import (
    load_service_maintainer_config,
)

global_config = load_config()

class ServiceMaintainer(ReActAgent):
    """low level agent"""
    
    def __init__(
        self, 
        name: str,
        model_config_name: str,
        system_prompt: str,
        max_iters: int = 10,
        verbose: bool = True,
    ) -> None:
        """Initialize the ReAct agent with the given name, model config name
        and tools.

        Args:
            name (`str`):
                The name of the agent.
            model_config_name (`str`):
                The name of the model config, which is used to load model from
                configuration.
            system_prompt (`str`):
                The system prompt of the agent.
            max_iters (`int`, defaults to `10`):
                The maximum number of iterations of the reasoning-acting loops.
            verbose (`bool`, defaults to `True`):
                Whether to print the detailed information during reasoning and
                acting steps. If `False`, only the content in speak field will
                be print out.
        """
        service_toolkit = ServiceToolkit()
        service_toolkit.add(execute_python_code, use_docker=False)
        service_toolkit.add(execute_shell_command)
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            sys_prompt=system_prompt,
            service_toolkit=service_toolkit,
            max_iters=max_iters,
            verbose=verbose,
        )

    @staticmethod
    def _init_from_config(service_name: str, model_config_name: str) -> None:
        """
        """
        service_maintainer_config = load_service_maintainer_config(global_config['project']['name'], service_name)
        prompter = Prompter()
        prompter.load_prompt_template(global_config['agent']['service_prompt_template_path'])
        prompter.fill_system_message(service_maintainer_config)
        agent = ServiceMaintainer(
            name=service_name,
            model_config_name=model_config_name,
            system_prompt=prompter.system_message,
        )
        return agent

    def __repr__(self):
        return (
            f"ServiceMaintainer({self.name})\n "
            f"Description: {self.description}\n backend: {self.model}"
        )