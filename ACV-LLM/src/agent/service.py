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

global_config = load_config()

class ServiceMaintainer(SocietyOfMindAgent):
    '''
    A ServiceMaintainer is a SocietyOfMindAgent that manages a group chat with two agents: an assistant and a code executor.
    Every ServiceMaintainer maintains a microservice component in the system.
    '''
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
        '''
        Initialize a ServiceMaintainer.
        - param service_name: The name of the service.
        - param service_description: The description of the service.
        - param system_message: The system message that will be displayed to the user.
        - param human_input_mode: The mode of human input. Default is "NEVER".
        - param is_termination_msg: The termination message. Default is TERMINATE.
        - param max_turns: The maximum number of turns in the conversation. Default is 100.
        - param cache_seed: The cache seed for the model. Default is 42.
        - param kwargs: Additional keyword arguments.
        '''
        llm_config = load_llm_config(cache_seed)

        class ServiceMaintainerAgent(ConversableAgent):
            def __init__(self):
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
                self.__steps += 1
                print(f'==================== Step {self.__steps} ====================')
                return super()._process_received_message(message, sender, silent)

        assistant = ServiceMaintainerAgent()

        code_executor = UserProxyAgent(
            f"{service_name}-code-executor",
            human_input_mode="NEVER",
            code_execution_config={
                "work_dir": global_config['base_path'],
                "use_docker": False,
                "timeout": 240,
            },
            default_auto_reply="",
            is_termination_msg=is_termination_msg,
        )

        groupchat = GroupChat(
            agents=[assistant, code_executor],
            admin_name=f'{service_name}-assistant',
            messages=[],
            speaker_selection_method="round_robin",  # With two agents, this is equivalent to a 1:1 conversation.
            allow_repeat_speaker=False,
            max_round=max_turns,
        )

        manager = GroupChatManager(
            groupchat=groupchat,
            name=f'{service_name}-group-manager',
            system_message="""
                You are a group chat mananger to maintain a microservice component.
                Your task is transfer messages to group members and manage the conversation.
                When you are ready to terminate the chat, please type 'TERMINATE' to end the conversation.
            """,
            llm_config=llm_config,
        )

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
        '''
        Init ServiceMaintainer from service_maintainers.yaml
        - param service_name: str, the name of the service.
        - param cache_seed: int | None, the cache seed for the model. Default is 42.
        - param is_termination_msg: Optional[Callable[[Dict], bool]], the termination message. Default is TERMINATE.
        '''
        service_maintainer_config = load_service_maintainer_config(global_config['project']['name'], service_name)
        prompter = Prompter()
        prompter.load_prompt_template(global_config['agent']['service_prompt_template_path'])
        prompter.fill_system_message(service_maintainer_config)
        prompter.generate_function_descriptions(service_maintainer_config['tool_functions_path'])
        agent = ServiceMaintainer(
            service_name=service_maintainer_config['service_name'],
            service_description=service_maintainer_config['service_description'],
            system_message=prompter.system_message,
            is_termination_msg=is_termination_msg,
            cache_seed=cache_seed,
        )
        return agent

    def __repr__(self):
        return f"ServiceMaintainer({self.name})\n Description: {self.description}\n backend: {self.model}"