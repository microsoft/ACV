# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import argparse
import contextlib

from datetime import datetime
from autogen import UserProxyAgent

from .module import load_config, Logger
from .agent import ServiceMaintainer

logger = Logger(__file__, 'INFO')
global_config = load_config()


def parse_args():
    parser = argparse.ArgumentParser(description='Run working machanism 1')
    parser.add_argument('--task', type=str, help='Task to send to the component.', required=True)
    parser.add_argument('--component', type=str, help='Component with agent to solve the task.', required=True)
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for the agent. Default is 42, use -1 to disable cache seed.')
    return parser.parse_args()

def main(args: argparse.Namespace):
    result_dir = global_config['result_path']
    log_file = os.path.join(result_dir, f'{args.component}.md')
    service_maintainers_config = load_config('service_maintainers.yaml')
    project = global_config['project']['name']
    service_maintainers = list(service_maintainers_config[project].keys())
    if args.component not in service_maintainers:
        raise ValueError(f'Invalid component {args.component}. Must be one of {service_maintainers}')

    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=args.component,
        cache_seed=args.cache_seed if args.cache_seed != -1 else None
    )

    maintainer = UserProxyAgent(
        name=f'Maintainer',
        human_input_mode='NEVER',
        code_execution_config=False,
        default_auto_reply='',
        is_termination_msg=lambda x: True,
    )

    logger.warning(f'See log file to get the chat history: {log_file}')

    with contextlib.redirect_stdout(open(log_file, 'w')):
        maintainer.initiate_chat(service_maintainer, message=args.task)

    logger.info('Task execution completed.')

if __name__ == '__main__':
    logger.info('Before running the script, make sure the services in your k8s evnironment are running')
    args = parse_args()
    main(args)