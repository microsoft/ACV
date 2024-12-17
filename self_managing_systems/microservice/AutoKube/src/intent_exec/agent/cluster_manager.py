# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from typing import Literal
from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent
from autogen import (
    ConversableAgent,
    UserProxyAgent,
    GroupChat,
    GroupChatManager
)

from ..module import Prompter

from .utils import (
    load_gpt_4_turbo_config,
    TERMINATE,
    AWAITING_FLAG
)
from ..module.utils import get_ancestor_path

# Base path for relative directory resolution
base_path = get_ancestor_path(2)

class ClusterManager(SocietyOfMindAgent):
    """
    A ClusterManager coordinates the tasks across multiple agents in a microservice environment.
    It manages communication flow, task execution, and termination conditions using a group chat mechanism.
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
        Initialize the ClusterManager agent.

        Parameters:
        - name (str): The name of the cluster manager.
        - description (str): A brief description of the cluster manager's role.
        - system_message (str): The system message displayed to guide the agent behavior.
        - human_input_mode (Literal["ALWAYS", "NEVER", "TERMINATE"]): Specifies when human input is required.
          Default is "NEVER".
        - max_turns (int): The maximum number of turns allowed in the group chat. Default is 40.
        - cache_seed (int | None): The random seed for caching model outputs. Default is 42.
        - kwargs: Additional arguments for parent class initialization.
        """
        self.description = description
        llm_config = load_gpt_4_turbo_config(cache_seed=cache_seed)

        # Inner ConversableAgent for planning and message processing
        class ClusterManagerAgent(ConversableAgent):
            """
            A nested agent responsible for planning tasks and processing messages.
            It tracks the conversation steps and handles message flow.
            """
            def __init__(self):
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
                Process incoming messages and print the current step for tracking.

                Parameters:
                - message: The received message content.
                - sender: The sender of the message.
                - silent: Whether to suppress output.
                """
                self.__steps += 1
                print(f'==================== Step {self.__steps} ====================')
                return super()._process_received_message(message, sender, silent)

        # Initialize planner agent
        planner = ClusterManagerAgent()

        # Initialize code executor agent for running code tasks
        code_executor = UserProxyAgent(
            f"{name}-code-executor",
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": base_path,
                "use_docker": False,
                "timeout": 120,
            },
            default_auto_reply="",
            is_termination_msg=(
                lambda x: 
                TERMINATE(x) 
                or x.get('content', '').strip() == "" 
                or x.get('content', '').find(AWAITING_FLAG) != -1
            ),
        )

        # Set up group chat between planner and code executor
        groupchat = GroupChat(
            agents=[planner, code_executor],
            admin_name=f'{name}-planner',
            messages=[],
            speaker_selection_method="round_robin",  # Alternates between two agents
            allow_repeat_speaker=False,
            max_round=max_turns,
        )

        # GroupChatManager manages the overall group chat behavior
        manager = GroupChatManager(
            groupchat=groupchat,
            name=f'{name}-group-manager',
            system_message="""
                You are a group chat manager responsible for maintaining a microservice component.
                Your role includes transferring messages among group members and managing the conversation.
                Type 'TERMINATE' when the conversation should end.
            """,
            llm_config=llm_config,
        )

        # Initialize the parent class with the group manager
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
        Initialize a ClusterManager instance from a configuration file.

        Parameters:
        - cache_seed (int | None): The random seed for caching model outputs. Default is 42.
        - components (list[str]): A list of components managed by the cluster.

        Returns:
        - ClusterManager: An initialized ClusterManager instance.
        """
        prompter = Prompter()
        # Load system message template
        prompter.load_prompt_template(os.path.join(base_path, 'prompts/cluster_manager.yaml'))
        prompter.fill_system_message({
            "service_list": components
        })
        # Generate function descriptions for the cluster manager
        prompter.generate_function_descriptions(os.path.join(base_path, 'intent_exec/agent/tool_functions_for_manager.py'))
        
        description = 'Cluster manager service. It controls task distribution among service maintainers.'
        return ClusterManager(
            name='manager',
            description=description,
            system_message=prompter.system_message,
            cache_seed=cache_seed,
        )
