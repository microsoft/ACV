# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
import argparse
from datetime import datetime

from .module import (
    Selector,
    ChaosFactory,
    ChaosInjector,
    RabbitMQ,
    Logger,
    load_yaml,
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

# Initialize the logger
logger = Logger(__file__, 'INFO')

# Load global configuration
global_config = load_config()

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including instance, components, timeout, and cache seed.
    """
    parser = argparse.ArgumentParser(description='Run high-level experiments for L1/2 tasks.')
    parser.add_argument(
        '--instance', type=str, required=True,
        help='Name of the test case instance. Note: Only test cases in L3/4/5 can be run here. Traffic is ignored in this setting.'
    )
    parser.add_argument(
        '--components', type=str, required=True,
        help='Components to run in this task, split by comma.'
    )
    parser.add_argument(
        '--timeout', type=int, default=900,
        help='The time limit for the task in seconds. Default is 900 seconds.'
    )
    parser.add_argument(
        '--cache_seed', type=int, default=42,
        help='Cache seed for agents. Default is 42, use -1 to disable cache seed.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to execute the specified task.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    logger.info('Starting the task...')
    instance = args.instance
    test_case = load_yaml(os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))

    now_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    result_dir = os.path.join(global_config['base_path'], global_config['result_path'], now_time)
    os.makedirs(result_dir, exist_ok=True)

    # Set up the environment
    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(
        global_config['project']['deployment'], 
        logger=logger
    )
    environment_manager.setup(config_fpath=os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    environment_manager.check_pods_ready()
    
    # Start traffic loader
    traffic_loader = TrafficLoader(
        component='front-end',
        namespace='sock-shop',
        mode=test_case['workload'],
        logger=logger
    )
    traffic_loader.start()
    logger.info('Waiting for traffic to be ready...')
    # time.sleep(240)  # Allow time for traffic to stabilize

    # Handle chaos experiments if specified
    chaos_factory = ChaosFactory.get_instance()
    if 'chaos' in test_case:
        chaos_config = test_case['chaos']
        logger.info(f'Running test case {instance} with chaos experiment.')
        selector = Selector(**chaos_config['selector'])
        chaos = chaos_factory.get_experiment(
            e=chaos_config['type'],
            name=chaos_config['name'],
            namespace=test_case['namespace'],
            selector=selector,
            **chaos_config['args']
        )
        
        chaos_injector = ChaosInjector(chaos=chaos, logger=logger)
        chaos_injector.start_experiment()
        # time.sleep(60)  # Allow time for the chaos experiment to take effect

    components = args.components.split(',')

    # Initialize cluster manager and service maintainers
    cluster_manager = ClusterManager._init_from_config(
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
        components=components
    )
    manager_consumer = ManagerConsumer(
        agent=cluster_manager,
        log_file_path=os.path.join(result_dir, 'manager.md')
    )

    # Validate service maintainers and initialize their agents
    service_maintainers_config = load_config('service_maintainers.yaml')
    service_maintainers = list(service_maintainers_config[global_config['project']['name']].keys())
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

    # Set up RabbitMQ and publish the task message
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
    queues = global_config['rabbitmq']['manager']['queues']
    for queue in queues:
        rabbitmq.add_queue(**queue)
    
    task = f'{global_config["heartbeat"]["group_task_prefix"]}{global_config["heartbeat"]["task"]}'
    rabbitmq.publish(task, routing_keys=['manager'])

    # Task execution loop
    try:
        time.sleep(args.timeout)
    except KeyboardInterrupt:
        logger.warning("Connection closed by user.")
    finally:
        logger.info('Task execution complete.')
        message_collector.stop()
        manager_consumer.stop()
        if 'chaos' in test_case:
            chaos_injector.delete_experiment()
        for service_maintainer_consumer in service_maintainer_consumers:
            service_maintainer_consumer.stop()

    # Cleanup
    logger.info('Stopping the task...')
    traffic_loader.stop()
    environment_manager.teardown()

if __name__ == '__main__':
    args = parse_args()
    main(args)
