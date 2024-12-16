# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import argparse
import contextlib
from datetime import datetime
from autogen import UserProxyAgent

from .module import load_config, Logger
from .agent import ServiceMaintainer

# Initialize logger and load global configuration
logger = Logger(__file__, 'INFO')
global_config = load_config()

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including task, component, and cache_seed.
    """
    parser = argparse.ArgumentParser(description='Run working mechanism 1')
    parser.add_argument(
        '--task', type=str, required=True,
        help='Task to send to the component.'
    )
    parser.add_argument(
        '--component', type=str, required=True,
        help='Component with an agent to solve the task.'
    )
    parser.add_argument(
        '--cache_seed', type=int, default=42,
        help='Cache seed for the agent. Default is 42, use -1 to disable cache seed.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to execute a task using a ServiceMaintainer agent.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    # Define result directory and log file path
    result_dir = global_config['result_path']
    log_file = os.path.join(result_dir, f'{args.component}.md')

    # Load service maintainer configuration and validate the component
    service_maintainers_config = load_config('service_maintainers.yaml')
    project = global_config['project']['name']
    service_maintainers = list(service_maintainers_config[project].keys())
    if args.component not in service_maintainers:
        raise ValueError(f'Invalid component "{args.component}". Must be one of {service_maintainers}.')

    # Initialize the ServiceMaintainer agent
    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=args.component,
        cache_seed=args.cache_seed if args.cache_seed != -1 else None
    )

    # Initialize the UserProxyAgent to communicate with the ServiceMaintainer
    maintainer = UserProxyAgent(
        name='Maintainer',
        human_input_mode='NEVER',
        code_execution_config=False,
        default_auto_reply='',
        is_termination_msg=lambda x: True,
    )

    logger.warning(f'See log file to get the chat history: {log_file}')

    # Redirect stdout to log file and initiate chat
    with contextlib.redirect_stdout(open(log_file, 'w')):
        maintainer.initiate_chat(service_maintainer, message=args.task)

    logger.info('Task execution completed.')

if __name__ == '__main__':
    # Display a warning to ensure Kubernetes services are running
    logger.info('Before running the script, ensure the services in your Kubernetes environment are running.')
    args = parse_args()
    main(args)
