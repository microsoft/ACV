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

global_config = load_config()

class ClusterManager(SocietyOfMindAgent):

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
        Initialize a cluster manager.
        - param name: The name of the cluster manager.
        - param description: The description of the cluster manager.
        - param system_message: The system message that will be displayed to the user.
        - param human_input_mode: The mode of human input. Default is "NEVER".
        - param max_turns: The maximum number of turns in the conversation. Default is 40.
        - param cache_seed: The cache seed for the model. Default is 42.
        """
        self.description = description
        llm_config = load_llm_config(cache_seed=cache_seed)

        class ClusterManagerAgent(ConversableAgent):
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
                self.__steps += 1
                print(f'==================== Step {self.__steps} ====================')
                return super()._process_received_message(message, sender, silent)


        planner = ClusterManagerAgent()

        code_executor = UserProxyAgent(
            f"{name}-code-executor",
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": global_config['base_path'],
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

        groupchat = GroupChat(
            agents=[planner, code_executor],
            admin_name=f'{name}-planner',
            messages=[],
            speaker_selection_method="round_robin",  # With two agents, this is equivalent to a 1:1 conversation.
            allow_repeat_speaker=False,
            max_round=max_turns,
        )

        manager = GroupChatManager(
            groupchat=groupchat,
            name=f'{name}-group-manager',
            system_message="""
                You are a group chat mananger to maintain a microservice component.
                Your task is transfer messages to group members and manage the conversation.
                When you are ready to terminate the chat, please type 'TERMINATE' to end the conversation.
            """,
            llm_config=llm_config,
        )

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
        Initialize a cluster manager from a configuration file.
        - param name: str, The name of the cluster manager.
        - param cache_seed: int | None, The cache seed for the model. Default is 42.
        - param model: str, The model to use for the conversation. Default is 'gpt4-1'.
        """
        prompter = Prompter()
        prompter.load_prompt_template(global_config['agent']['manager_prompt_template_path'])
        prompter.fill_system_message({
            "namespace": global_config['project']['namespace'],
            "service_maintainers": components
        })
        prompter.generate_function_descriptions(global_config['agent']['manager_tool_functions_path'])
        description = 'Cluster manager service. It control how the tasks are distributed among the service maintainers.'
        return ClusterManager(
            name='manager',
            description=description,
            system_message=prompter.system_message,
            cache_seed=cache_seed,
        )