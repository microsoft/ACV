# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Literal
from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent
from autogen import (
    ConversableAgent,
    UserProxyAgent,
    GroupChat,
    GroupChatManager
)

from ..module import (
    load_config,
    Prompter
)
from .utils import (
    load_llm_config,
    TERMINATE,
    AWAITING_FLAG
)

# Load global configuration settings
global_config = load_config()

class ClusterManager(SocietyOfMindAgent):
    """
    ClusterManager is a specialized agent that manages interactions within a microservice-based system.
    It orchestrates communication between components and supports task distribution and execution.
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_message: str,
        human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
        max_turns: int = 40,
        cache_seed: int | None = 42,
        **kwargs
    ):
        """
        Initialize a ClusterManager instance.
        
        Parameters:
        - name (str): The name of the cluster manager.
        - description (str): A brief description of the cluster manager's purpose.
        - system_message (str): A predefined message to guide system behavior and communication.
        - human_input_mode (Literal["ALWAYS", "NEVER", "TERMINATE"]): Determines how human input is handled. Default is "NEVER".
        - max_turns (int): The maximum number of conversation turns before termination. Default is 40.
        - cache_seed (int | None): Seed value for model caching. Default is 42.
        - kwargs: Additional keyword arguments passed to the parent class.
        """
        self.description = description

        # Load configuration for the language model (LLM)
        llm_config = load_llm_config(cache_seed=cache_seed)

        class ClusterManagerAgent(ConversableAgent):
            """
            Inner class for a Cluster Manager Agent that plans and processes messages.
            """

            def __init__(self):
                """
                Initialize the planning agent for the cluster manager.
                """
                self.__steps = 0
                super().__init__(
                    name=f"{name}-planner",
                    system_message=system_message,
                    human_input_mode="NEVER",
                    llm_config=llm_config,
                    max_consecutive_auto_reply=max_turns,
                    is_termination_msg=lambda x: x.get('content', '').find(AWAITING_FLAG) != -1,
                )
            
            def _process_received_message(self, message, sender, silent):
                """
                Process messages received by the agent.

                Parameters:
                - message: The content of the message received.
                - sender: The sender of the message.
                - silent: Boolean indicating if the process should be silent.
                """
                self.__steps += 1
                print(f'==================== Step {self.__steps} ====================')
                return super()._process_received_message(message, sender, silent)

        # Define the planning agent
        planner = ClusterManagerAgent()

        # Define a code execution agent
        code_executor = UserProxyAgent(
            f"{name}-code-executor",
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": global_config['base_path'],  # Working directory for code execution
                "use_docker": False,  # Whether to use Docker for isolation
                "timeout": 120,  # Timeout in seconds for execution
            },
            default_auto_reply="",
            is_termination_msg=(
                lambda x: 
                TERMINATE(x) 
                or x.get('content', '').strip() == "" 
                or x.get('content', '').find(AWAITING_FLAG) != -1
            ),
        )

        # Define a group chat for the agents
        groupchat = GroupChat(
            agents=[planner, code_executor],
            admin_name=f'{name}-planner',
            messages=[],
            speaker_selection_method="round_robin",  # Alternate speaking turns between agents.
            allow_repeat_speaker=False,
            max_round=max_turns,
        )

        # Define the group chat manager
        manager = GroupChatManager(
            groupchat=groupchat,
            name=f'{name}-group-manager',
            system_message="""
                You are a group chat manager to maintain a microservice component.
                Your task is to transfer messages to group members and manage the conversation.
                When you are ready to terminate the chat, please type 'TERMINATE' to end the conversation.
            """,
            llm_config=llm_config,
        )

        # Initialize the parent class with the chat manager
        super().__init__(
            name,
            chat_manager=manager,
            llm_config=llm_config,
            human_input_mode=human_input_mode,
            **kwargs
        )

    @staticmethod
    def _init_from_config(cache_seed: int | None = 42, components: list[str] = []):
        """
        Static method to initialize a ClusterManager using a configuration file.
        
        Parameters:
        - cache_seed (int | None): Seed value for model caching. Default is 42.
        - components (list[str]): List of components maintained by the manager.
        
        Returns:
        - ClusterManager: An initialized ClusterManager instance.
        """
        prompter = Prompter()

        # Load and populate the system message template
        prompter.load_prompt_template(global_config['agent']['manager_prompt_template_path'])
        prompter.fill_system_message({
            "namespace": global_config['project']['namespace'],
            "service_maintainers": components
        })

        # Generate function descriptions
        prompter.generate_function_descriptions(global_config['agent']['manager_tool_functions_path'])

        # Description for the ClusterManager
        description = 'Cluster manager service. It controls how tasks are distributed among the service maintainers.'

        # Return a configured instance of ClusterManager
        return ClusterManager(
            name='manager',
            description=description,
            system_message=prompter.system_message,
            cache_seed=cache_seed,
        )
