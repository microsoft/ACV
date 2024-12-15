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

logger = Logger(__file__, 'INFO')

global_config = load_config()

def parse_args():
    parser = argparse.ArgumentParser(description='Run high level experiments for L1/2 tasks.')
    parser.add_argument('--instance', type=str, help='Name of the test case instance. Note that only test case in L3/4/5 can be run here. Note that traffic is ignored in this setting.', required=True)
    parser.add_argument('--components', type=str, help='Components to run in this task, split by comma.', required=True)
    parser.add_argument('--timeout', type=int, default=900, help='The time limit for the task.')
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for agents. Default is 42, use -1 to disable cache seed.')
    
    return parser.parse_args()

def main(args: argparse.Namespace):
    logger.info('Starting the task...')
    instance = args.instance
    test_case = load_yaml(os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))

    now_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    result_dir = os.path.join(global_config['base_path'], global_config['result_path'], now_time)
    os.makedirs(result_dir, exist_ok=True)

    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(global_config['project']['deployment'], logger=logger)
    environment_manager.setup(config_fpath=os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    environment_manager.check_pods_ready()
    
    traffic_loader = TrafficLoader(
        component='front-end',
        namespace='sock-shop',
        mode=test_case['workload'],
        logger=logger
    )
    traffic_loader.start()
    logger.info('Waiting for traffic to be ready...')

    # wait for traffic to be ready
    time.sleep(240)

    chaos_factory = ChaosFactory.get_instance()

    if 'chaos' in test_case:
        chaos_config = test_case['chaos']
        logger.info(f'Running test case {instance}')
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
        
        # wait for chaos to be ready
        time.sleep(60)

    components = args.components.split(',')

    # initialize the cluster manager and service maintainers
    cluster_manager = ClusterManager._init_from_config(
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
        components=components
    )

    manager_consumer = ManagerConsumer(
        agent=cluster_manager,
        log_file_path=os.path.join(result_dir, 'manager.md')
    )

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

    message_collector = MessageCollector()

    message_collector.start()

    for service_maintainer_consumer in service_maintainer_consumers:
        service_maintainer_consumer.start()

    manager_consumer.start()

    logger.warning(f'Chat history is stored in directory: {result_dir}')

    rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
    queues = global_config['rabbitmq']['manager']['queues']
    for queue in queues:
        rabbitmq.add_queue(**queue)
    
    task = f'{global_config["heartbeat"]["group_task_prefix"]}{global_config["heartbeat"]["task"]}'
    rabbitmq.publish(task, routing_keys=['manager'])

    try:
        time.sleep(args.timeout)
    except KeyboardInterrupt:
        logger.warning("Connection closed.")
    finally:
        logger.info(f'Task execute complete.')
        message_collector.stop()
        manager_consumer.stop()
        if 'chaos' in test_case:
            chaos_injector.delete_experiment()
        for service_maintainer_consumer in service_maintainer_consumers:
            service_maintainer_consumer.stop()

    logger.info('Stopping the task...')
    traffic_loader.stop()
    environment_manager.teardown()

if __name__ == '__main__':
    args = parse_args()
    main(args)