# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import logging
import colorlog
from typing import Union
from .utils import load_config

# Load global configuration
global_config = load_config()

# Define log level colors for console output
color_map = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}

class Logger(logging.Logger):
    """
    Custom logger class that supports both file and console logging with colored output.

    Parameters:
    - filename (str): The name of the file where logs will be saved.
    - level (Union[int, str]): The logging level (e.g., DEBUG, INFO, WARNING). Default is 0.
    """

    def __init__(self, filename: str, level: Union[int, str] = 0) -> None:
        # Validate and set logging level
        if isinstance(level, str):
            try:
                level = getattr(logging, level.upper())
            except AttributeError:
                print('WARNING: Invalid log level, using logging.INFO as default.')
                level = logging.INFO
        super().__init__(os.path.basename(filename), level)

        # Set logger level
        self.setLevel(level)

        # Setup file handler for logging to a file
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_file_path = os.path.join(
            global_config['logging_path'], 
            os.path.splitext(os.path.basename(filename))[0] + '.log'
        )
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        self.addHandler(file_handler)

        # Setup console handler for logging to the terminal with colored output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors=color_map
        )
        console_handler.setFormatter(console_formatter)
        self.addHandler(console_handler)

        # Info log for initialization
        self.info(f"Logger initialized with level: {logging.getLevelName(level)}")
