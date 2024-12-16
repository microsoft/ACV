# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal, Optional, Dict, Callable
from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent
from ..module import (
    load_config,
    Prompter
)
from autogen import (
    ConversableAgent, 
    UserProxyAgent, 
    GroupChat, 
    GroupChatManager,
)
from .utils import (
    load_llm_config,
    load_service_maintainer_config,
    TERMINATE
)

# Load global configuration settings
global_config = load_config()

class ServiceMaintainer(SocietyOfMindAgent):
    """
    ServiceMaintainer is a SocietyOfMindAgent that manages a microservice component
    through a group chat involving an assistant, a code executor.
    """

    def __init__(
        self,
        service_name: str,
        service_description: str,
        system_message: str,
        human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
        is_termination_msg: Optional[Callable[[Dict], bool]] = TERMINATE,
        max_turns: int = 100,
        cache_seed: int | None = 42,
        **kwargs
    ):
        """
        Initialize a ServiceMaintainer agent.

        Parameters:
        - service_name (str): The name of the microservice being managed.
        - service_description (str): A description of the microservice.
        - system_message (str): The system-level prompt for the assistant agent.
        - human_input_mode (Literal["ALWAYS", "NEVER", "TERMINATE"]): How human input is handled. Default is "NEVER".
        - is_termination_msg (Optional[Callable[[Dict], bool]]): A function to determine when to terminate the chat. Default is TERMINATE.
        - max_turns (int): Maximum conversation turns allowed. Default is 100.
        - cache_seed (int | None): Seed for caching the language model. Default is 42.
        - kwargs: Additional keyword arguments.
        """
        # Load LLM configuration using the provided cache seed
        llm_config = load_llm_config(cache_seed)
        self.service_name = service_name

        # Define the assistant agent
        class ServiceMaintainerAgent(ConversableAgent):
            """
            The assistant agent responsible for reasoning and planning actions for the service.
            """

            def __init__(self):
                """
                Initialize the assistant agent.
                """
                self.__steps: int = 0
                super().__init__(
                    name=f'{service_name}-assistant',
                    system_message=system_message,
                    max_consecutive_auto_reply=max_turns,
                    human_input_mode="NEVER",
                    llm_config=llm_config,
                    **kwargs
                )

            def _process_received_message(self, message, sender, silent):
                """
                Process messages received by the assistant.

                Parameters:
                - message: The message content received.
                - sender: The sender of the message.
                - silent: If True, suppress output during processing.
                """
                self.__steps += 1
                print(f'==================== Step {self.__steps} ====================')
                return super()._process_received_message(message, sender, silent)

        # Instantiate the assistant agent
        self.assistant = ServiceMaintainerAgent()

        # Define the code executor agent
        self._code_executor = UserProxyAgent(
            f"{service_name}-code-executor",
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": global_config['base_path'],  # Working directory for executing code
                "use_docker": False,  # Docker is not used for isolation
                "timeout": 240,  # Timeout for code execution in seconds
                "last_n_messages": 10,  # Number of messages to keep for context
            },
            default_auto_reply="",
            is_termination_msg=is_termination_msg,
        )

        # Define the group chat for interaction
        groupchat = GroupChat(
            agents=[self.assistant, self._code_executor],
            admin_name=f'{service_name}-assistant',
            messages=[],
            speaker_selection_method='round_robin',  # Alternate turns between agents
            allow_repeat_speaker=False,
            max_round=max_turns,
        )

        # Define the group chat manager
        manager = GroupChatManager(
            groupchat=groupchat,
            name=f'{service_name}-group-manager',
            system_message="""
                You are a group chat manager to maintain a microservice component.
                Your task is to transfer messages to group members and manage the conversation.
                When you are ready to terminate the chat, please type 'TERMINATE' to end the conversation.
            """,
            llm_config=llm_config,
        )

        # Initialize the parent class with the chat manager
        super().__init__(
            service_name,
            chat_manager=manager,
            llm_config=llm_config,
            human_input_mode=human_input_mode,
            **kwargs
        )
        self.description = service_description

    @staticmethod
    def _init_from_config(service_name: str, cache_seed: int | None = 42, is_termination_msg: Optional[Callable[[Dict], bool]] = TERMINATE):
        """
        Static method to initialize a ServiceMaintainer from configuration.

        Parameters:
        - service_name (str): The name of the service being managed.
        - cache_seed (int | None): Seed for caching the language model. Default is 42.
        - is_termination_msg (Optional[Callable[[Dict], bool]]): A function to determine when to terminate the chat.

        Returns:
        - ServiceMaintainer: An initialized ServiceMaintainer agent.
        """
        # Load the service maintainer configuration
        service_maintainer_config = load_service_maintainer_config(global_config['project']['name'], service_name)

        # Initialize the prompter and load templates
        prompter = Prompter()
        prompter.load_prompt_template(global_config['agent']['service_prompt_template_path'])
        prompter.fill_system_message(service_maintainer_config)
        prompter.generate_function_descriptions(service_maintainer_config['tool_functions_path'])

        # Create and return the ServiceMaintainer instance
        agent = ServiceMaintainer(
            service_name=service_maintainer_config['service_name'],
            service_description=service_maintainer_config['service_description'],
            system_message=prompter.system_message,
            is_termination_msg=is_termination_msg,
            cache_seed=cache_seed,
        )
        return agent

    def __repr__(self):
        """
        Representation of the ServiceMaintainer instance.

        Returns:
        - str: A string representation of the agent, including its name, description, and backend model.
        """
        return (
            f"ServiceMaintainer({self.name})\n "
            f"Description: {self.description}\n backend: {self.model}"
        )
