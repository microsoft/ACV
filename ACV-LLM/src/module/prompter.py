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
    """
    The Prompter class handles the loading, customization, and generation of prompt templates for various tasks.
    It supports placeholders in system messages and user content, and provides tools for generating descriptions
    of functions from modules.
    """

    def __init__(self, prompt_template: str = ""):
        """
        Initialize the Prompter instance.

        Args:
        - prompt_template (str): Optional. Initial prompt template string.
        """
        self.prompt_template = prompt_template
        self._system_message = ""
        self._user_content = ""
        self._function_descptions = ""

    @property
    def system_message(self) -> str:
        """
        Get the fully constructed system message.

        Returns:
        - str: Combined system message and function descriptions.
        """
        return self._system_message + '\n' + self._function_descptions

    @property
    def user_content(self) -> str:
        """
        Get the user content message.

        Returns:
        - str: User content with placeholders filled.
        """
        return self._user_content
    
    def load_prompt_template(self, prompt_file: str):
        """
        Load a prompt template from a file.

        Args:
        - prompt_file (str): Path to the prompt template file.

        Raises:
        - FileNotFoundError: If the specified file does not exist.
        """
        file_path = os.path.join(global_config['prompt_path'], prompt_file)
        if os.path.exists(file_path):
            self.prompt = load_yaml(file_path)
            # Pre-fill system message and user content if no placeholders are present.
            if 'system' in self.prompt:
                self._system_message = self.prompt['system']
            if 'user' in self.prompt:
                self._user_content = self.prompt['user']
        else:
            raise FileNotFoundError(f"Prompt template not found at {prompt_file}")
        
    def fill_system_message(self, placeholders: dict):
        """
        Fill the system message placeholders with actual values.

        Args:
        - placeholders (dict): A dictionary containing placeholder keys and their replacement values.
        """
        template = Template(self.prompt['system'])
        self._system_message = template.render(**placeholders)
    
    def fill_user_content(self, placeholders: dict):
        """
        Fill the user content placeholders with actual values.

        Args:
        - placeholders (dict): A dictionary containing placeholder keys and their replacement values.
        """
        template = Template(self.prompt['user'])
        self._user_content = template.render(**placeholders)

    def generate_function_descriptions(self, tool_functions_path: str):
        """
        Generate descriptions for functions in the provided module to include in the prompt.

        Args:
        - tool_functions_path (str): Path to the Python file containing tool functions.
        """
        def load_module(module_path: str):
            """
            Dynamically load a module from the specified file path.

            Args:
            - module_path (str): The file path of the module.

            Returns:
            - module: The loaded module.
            """
            spec = importlib.util.spec_from_file_location("module_name", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        def convert_path_to_module(module_path: Path) -> str:
            """
            Convert a file path to a module-like string for imports.

            Args:
            - module_path (Path): The file path of the module.

            Returns:
            - str: The module-like string.
            """
            return ".".join(module_path.with_suffix("").parts)
        
        # Load the module and extract functions.
        module = load_module(tool_functions_path)
        functions = module.__dict__.get('functions', [])
        model_name = convert_path_to_module(Path(tool_functions_path))

        # Generate function descriptions for prompts using an executor.
        executor = LocalCommandLineCodeExecutor(
            work_dir=global_config['base_path'], 
            functions=functions
        )
        prompt_template = f"""
        # Introduction for Tool Functions
        - You have access to the following tool functions. They can be accessed from the module called `{model_name}` by their function names.

        - For example, if there was a function called `foo` you could import it by writing `from {model_name} import foo`

        $functions
        """
        self._function_descptions = executor.format_functions_for_prompt(prompt_template=prompt_template)
