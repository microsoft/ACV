# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import logging
import colorlog

from typing import Union
from .utils import load_config
from .utils import get_ancestor_path

base_path = get_ancestor_path(2)

color_map = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}

class Logger(logging.Logger):

    def __init__(self, filename: str, level: Union[int | str] = 0) -> None:
        if isinstance(level, str):
            try:
                level = getattr(logging, level)
            except AttributeError:
                print('WARNING: Invalid log level, using logging.INFO as default.')
                level = logging.INFO
        super().__init__(os.path.basename(filename), level)

        self.setLevel(level)

        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler = logging.FileHandler(os.path.join(base_path, 'logs', os.path.splitext(os.path.basename(filename))[0] + '.log'))
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        self.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors=color_map
        )
        console_handler.setFormatter(console_formatter)
        self.addHandler(console_handler)