# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
import argparse
from datetime import datetime

from .module import (
    RabbitMQ,
    Logger,
    load_config, 
    ManagerConsumer, 
    TrafficLoader,
    EnvironmentManagerFactory,
    ServiceMaintainerConsumer,
    MessageCollector
)
from .agent import (
    ClusterManager,
    ServiceMaintainer,
)

# Initialize logger
logger = Logger(__file__, 'INFO')

# Load global configuration
global_config = load_config()

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including task description, components, timeout, and cache seed.
    """
    parser = argparse.ArgumentParser(
        description='Run high-level experiments for L1/2 tasks.'
    )
    parser.add_argument(
        '--task', type=str, help='Task description.', required=True
    )
    parser.add_argument(
        '--components', type=str, help='Components to run in this task, split by comma.', required=True
    )
    parser.add_argument(
        '--timeout', type=int, default=900, help='Time limit for the task in seconds. Default is 900 seconds.'
    )
    parser.add_argument(
        '--cache_seed', type=int, default=42, help='Cache seed for agents. Default is 42, use -1 to disable cache seed.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to execute the task.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    logger.info('Starting the task...')
    now_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    result_dir = os.path.join(
        global_config['base_path'], 
        global_config['result_path'], 
        now_time
    )
    os.makedirs(result_dir, exist_ok=True)

    # Set up the environment manager
    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(
        global_config['project']['deployment'], 
        logger=logger
    )
    environment_manager.setup()
    environment_manager.check_pods_ready()
    
    # Start traffic loader
    traffic_loader = TrafficLoader(
        component='media-frontend',
        namespace='socical-network',
        mode='heavy',
        logger=logger
    )
    traffic_loader.start()
    logger.info('Waiting for traffic to be ready...')
    time.sleep(240)  # Wait for traffic to stabilize

    # Initialize cluster manager
    cluster_manager = ClusterManager._init_from_config(
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
        components=args.components.split(',')
    )

    manager_consumer = ManagerConsumer(
        agent=cluster_manager,
        log_file_path=os.path.join(result_dir, 'manager.md')
    )

    # Validate and initialize service maintainers
    service_maintainers_config = load_config('service_maintainers.yaml')
    service_maintainers = list(service_maintainers_config[global_config['project']['name']].keys())
    components = args.components.split(',')
    for component in components:
        if component not in service_maintainers:
            raise ValueError(f"Component {component} not found in service maintainers")

    agents = [
        ServiceMaintainer._init_from_config(
            service_name=component,
            cache_seed=args.cache_seed if args.cache_seed != -1 else None, 
        )
        for component in components
    ]

    service_maintainer_consumers = [
        ServiceMaintainerConsumer(
            agent=agent,
            log_file_path=os.path.join(result_dir, f'{agent.name}.md')
        )
        for agent in agents
    ]

    # Start message collection and consumers
    message_collector = MessageCollector()
    message_collector.start()

    for service_maintainer_consumer in service_maintainer_consumers:
        service_maintainer_consumer.start()

    manager_consumer.start()
    logger.warning(f'Chat history is stored in directory: {result_dir}')

    # Set up RabbitMQ queues and publish task message
    queues = global_config['rabbitmq']['manager']['queues']
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
    for queue in queues:
        rabbitmq.add_queue(**queue)
    rabbitmq.publish(f'TASK: {args.task}', routing_keys=['manager'])

    logger.info('Type Ctrl+C to stop the task manually.')
    try:
        time.sleep(args.timeout)
    except KeyboardInterrupt:
        logger.warning("Connection closed by user.")
    finally:
        logger.info('Task execution complete.')
        manager_consumer.stop()
        for service_maintainer_consumer in service_maintainer_consumers:
            service_maintainer_consumer.stop()
        message_collector.stop()

    logger.info('Stopping the task...')
    traffic_loader.stop()
    environment_manager.teardown()

if __name__ == '__main__':
    args = parse_args()
    main(args)
