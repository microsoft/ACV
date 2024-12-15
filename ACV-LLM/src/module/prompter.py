# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import importlib

from pathlib import Path
from jinja2 import Template
from autogen.coding import LocalCommandLineCodeExecutor

from .utils import load_yaml, load_config

global_config = load_config()

class Prompter:
    def __init__(self, prompt_template:str=""):
        self.prompt_template = prompt_template

        self._system_message = ""
        self._user_content = ""
        self._function_descptions = ""

    @property
    def system_message(self):
        return self._system_message + '\n' + self._function_descptions
    
    @property
    def critic_message(self):
        return self._critic_message

    @property
    def user_content(self):
        return self._user_content
    
    def load_prompt_template(self, prompt_file:str):
        '''
        Load a prompt template from file
        - param prompt_file: str, prompt template file
        '''
        if os.path.exists(os.path.join(global_config['prompt_path'], prompt_file)):
            self.prompt = load_yaml(os.path.join(global_config['prompt_path'], prompt_file))
            # prefill the system message and user content, so that we can use them directly if it contains no placeholders
            if 'system' in self.prompt:
                self._system_message = self.prompt['system']
            if 'critic' in self.prompt:
                self._critic_message = self.prompt['critic']
            if 'user' in self.prompt:
                self._user_content = self.prompt['user']
        else:
            raise FileNotFoundError(f"Prompt template not found at {prompt_file}")
        
    def fill_system_message(self, placeholders:dict):
        '''
        Fill the system message with placeholders
        - param placeholders: dict, dictionary of placeholders
        '''
        template = Template(self.prompt['system'])
        self._system_message = template.render(**placeholders)

    def fill_critic_message(self, placeholders:dict):
        '''
        Fill the critic message with placeholders
        - param placeholders: dict, dictionary of placeholders
        '''
        template = Template(self.prompt['critic'])
        self._critic_message = template.render(**placeholders)
    
    def fill_user_content(self, placeholders:dict):
        '''
        Fill the user content with placeholders
        - param placeholders: dict, dictionary of placeholders
        '''
        template = Template(self.prompt['user'])
        self._user_content = template.render(**placeholders)

    def generate_function_descriptions(self, tool_functions_path: str):
        def load_module(module_path: str):
            spec = importlib.util.spec_from_file_location("module_name", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        def convert_path_to_module(module_path: Path):
            module_path = ".".join(module_path.with_suffix("").parts)
            return module_path
        
        module = load_module(tool_functions_path)
        functions = module.__dict__['functions']
        model_name = convert_path_to_module(Path(tool_functions_path))

        executor = LocalCommandLineCodeExecutor(
            work_dir=global_config['base_path'], 
            functions=functions, 
        )
        prompt_template = f"""
        # Introduction for Tool Functions
        - You have access to the following tool functions. They can be accessed from the module called `{model_name}` by their function names.

        - For example, if there was a function called `foo` you could import it by writing `from {model_name} import foo`

        $functions
        """
        self._function_descptions = executor.format_functions_for_prompt(prompt_template=prompt_template)