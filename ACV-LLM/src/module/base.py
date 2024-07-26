# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from termcolor import colored
from logging import Logger
from pprint import pprint

from .utils import load_yaml, load_config
config = load_config()

class Base():
    def __init__(self, logger: Logger = None, verbose: bool = True, **kwargs: dict):
        self._logger = logger
        self._verbose = verbose

    @property
    def logger(self):
        return self._logger

    @logger.setter
    def logger(self, logger: Logger):
        self._logger = logger

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, verbose: bool):
        self._verbose = verbose

    def _print_with_color(self, message:str, color: str = 'white'):
        print(colored(message, color))

    def _log_with_terminal(self, method, message:str, pretty:bool = False, color: str = 'white'):
        if not self._verbose:
            return
        try:
            self.logger.__getattribute__(method)(message)
        except:
            if pretty:
                pprint(message)
            else:
                self._print_with_color(message, color)

    def debug(self, message:str, pretty:bool = False, color: str = 'white'):
        self._log_with_terminal('debug', message, pretty, color)

    def info(self, message:str, pretty:bool = False, color: str = 'green'):
        self._log_with_terminal('info', message, pretty, color)
            
    def warning(self, message:str, pretty:bool = False, color: str = 'yellow'):
        self._log_with_terminal('warning', message, pretty, color)

    def error(self, message:str, pretty:bool = False, color: str = 'red'):
        self._log_with_terminal('error', message, pretty, color)

    def critical(self, message:str, pretty:bool = False, color: str = 'red'):
        self._log_with_terminal('critical', message, pretty, color)

    def load_test_case(self, name: str):
        '''
        Load test case
        :param name: str, test case name
        '''
        test_case_path = os.path.join(config['data_path'], 'dataset', f'{name}.yaml')
        if not os.path.exists(test_case_path):
            raise FileNotFoundError(f'Test case {name} not found')
        workload = load_yaml(test_case_path)
        self.component = workload['component']
        self.namespace = workload['namespace']
        self.mode = workload['workload']