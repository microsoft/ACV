# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from termcolor import colored
from logging import Logger
from pprint import pprint
from .utils import load_yaml, load_config

config = load_config()

class Base:
    """
    A base class providing common utility functions for logging, verbose output,
    and loading test cases. Designed to be extended by other components in the system.
    """

    def __init__(self, logger: Logger = None, verbose: bool = True, **kwargs: dict):
        """
        Initialize the Base class.

        Parameters:
        - logger (Logger, optional): Logger instance for logging messages.
        - verbose (bool, optional): Enable or disable verbose output (default: True).
        - kwargs (dict): Additional keyword arguments for customization.
        """
        self._logger = logger
        self._verbose = verbose

    @property
    def logger(self):
        """Get the logger instance."""
        return self._logger

    @logger.setter
    def logger(self, logger: Logger):
        """Set the logger instance."""
        self._logger = logger

    @property
    def verbose(self):
        """Get the verbosity status."""
        return self._verbose

    @verbose.setter
    def verbose(self, verbose: bool):
        """Set the verbosity status."""
        self._verbose = verbose

    def _print_with_color(self, message: str, color: str = 'white'):
        """
        Print a message to the terminal with color.

        Parameters:
        - message (str): The message to print.
        - color (str, optional): The color for the message (default: 'white').
        """
        print(colored(message, color))

    def _log_with_terminal(self, method: str, message: str, pretty: bool = False, color: str = 'white'):
        """
        Log a message using the logger or print it to the terminal.

        Parameters:
        - method (str): The logging method (e.g., 'info', 'error').
        - message (str): The message to log.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'white').
        """
        if not self._verbose:
            return
        try:
            getattr(self.logger, method)(message)
        except AttributeError:
            if pretty:
                pprint(message)
            else:
                self._print_with_color(message, color)

    def debug(self, message: str, pretty: bool = False, color: str = 'white'):
        """
        Log a debug-level message or print it to the terminal.

        Parameters:
        - message (str): The debug message.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'white').
        """
        self._log_with_terminal('debug', message, pretty, color)

    def info(self, message: str, pretty: bool = False, color: str = 'green'):
        """
        Log an info-level message or print it to the terminal.

        Parameters:
        - message (str): The informational message.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'green').
        """
        self._log_with_terminal('info', message, pretty, color)

    def warning(self, message: str, pretty: bool = False, color: str = 'yellow'):
        """
        Log a warning-level message or print it to the terminal.

        Parameters:
        - message (str): The warning message.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'yellow').
        """
        self._log_with_terminal('warning', message, pretty, color)

    def error(self, message: str, pretty: bool = False, color: str = 'red'):
        """
        Log an error-level message or print it to the terminal.

        Parameters:
        - message (str): The error message.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'red').
        """
        self._log_with_terminal('error', message, pretty, color)

    def critical(self, message: str, pretty: bool = False, color: str = 'red'):
        """
        Log a critical-level message or print it to the terminal.

        Parameters:
        - message (str): The critical message.
        - pretty (bool, optional): Pretty-print the message (default: False).
        - color (str, optional): The color for the terminal message (default: 'red').
        """
        self._log_with_terminal('critical', message, pretty, color)

    def load_test_case(self, name: str):
        """
        Load a test case from a YAML file.

        Parameters:
        - name (str): The name of the test case.

        Raises:
        - FileNotFoundError: If the test case file is not found.

        Sets the following attributes:
        - component: The component associated with the test case.
        - namespace: The namespace of the test case.
        - mode: The workload mode of the test case.
        """
        test_case_path = os.path.join(config['data_path'], 'dataset', f'{name}.yaml')
        if not os.path.exists(test_case_path):
            raise FileNotFoundError(f'Test case {name} not found')

        workload = load_yaml(test_case_path)
        self.component = workload['component']
        self.namespace = workload['namespace']
        self.mode = workload['workload']
