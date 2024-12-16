# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
import argparse
from datetime import datetime

from .module import (
    ServiceMaintainerConsumer,
    MessageCollector,
    ManagerConsumer,
    load_config,
    RabbitMQ,
    Logger
)
from .agent import ServiceMaintainer, ClusterManager

# Initialize logger and load global configuration
logger = Logger(__file__, 'INFO')
global_config = load_config()

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including task, components, timeout, and cache_seed.
    """
    parser = argparse.ArgumentParser(description='Run working mechanism 2')
    parser.add_argument(
        '--task', type=str, required=True,
        help='Task to send to the high-level manager.'
    )
    parser.add_argument(
        '--components', type=str, required=True,
        help='Comma-separated list of components with agents to solve the task.'
    )
    parser.add_argument(
        '--timeout', type=int, default=900,
        help='Time limit for the task in seconds. Default is 900 seconds.'
    )
    parser.add_argument(
        '--cache_seed', type=int, default=42,
        help='Cache seed for agents. Default is 42, use -1 to disable cache seed.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to coordinate task execution with high-level and low-level agents.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    # Create a directory to store results
    now_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    result_dir = os.path.join(global_config['base_path'], global_config['result_path'], now_time)
    os.makedirs(result_dir, exist_ok=True)

    # Load service maintainer configuration and validate components
    service_maintainers_config = load_config('service_maintainers.yaml')
    project = global_config['project']['name']
    service_maintainers = list(service_maintainers_config[project].keys())

    components = args.components.split(',')
    for component in components:
        if component not in service_maintainers:
            raise ValueError(f'Invalid component "{component}". Must be one of {service_maintainers}.')

    # Initialize the high-level manager (ClusterManager)
    high_level_manager = ClusterManager._init_from_config(
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
        components=components
    )
    high_level_manager_consumer = ManagerConsumer(
        high_level_manager,
        log_file_path=os.path.join(result_dir, 'manager.md')
    )

    # Initialize low-level autonomic agents (ServiceMaintainers)
    low_level_autonomic_agents = [
        ServiceMaintainer._init_from_config(
            service_name=component,
            cache_seed=args.cache_seed if args.cache_seed != -1 else None
        )
        for component in components
    ]

    # Create consumers for low-level autonomic agents
    low_level_autonomic_agents_consumers = [
        ServiceMaintainerConsumer(
            agent,
            log_file_path=os.path.join(result_dir, f'{agent.name}.md')
        )
        for agent in low_level_autonomic_agents
    ]

    # Start message collector and consumers
    message_collector = MessageCollector()
    message_collector.start()

    for consumer in low_level_autonomic_agents_consumers:
        consumer.start()

    high_level_manager_consumer.start()

    logger.warning(f'Chat history is stored in directory: {result_dir}')

    # Set up RabbitMQ and publish the task
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
    queues = global_config['rabbitmq']['manager']['queues']
    for queue in queues:
        rabbitmq.add_queue(**queue)

    rabbitmq.publish(args.task, routing_keys=['manager'])

    # Execute task with timeout
    try:
        time.sleep(args.timeout)
    except KeyboardInterrupt:
        logger.warning("User interrupted the task.")

    logger.info('Task execution completed.')

if __name__ == '__main__':
    args = parse_args()
    main(args)
