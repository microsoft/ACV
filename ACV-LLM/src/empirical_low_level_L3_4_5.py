# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import time
import argparse

from .module import (
    load_config,
    load_yaml,
    RabbitMQ,
    ChaosFactory,
    ChaosInjector,
    TrafficLoader,
    Logger,
    Selector,
    EnvironmentManager,
    ServiceMaintainerConsumer
)
from .agent import ServiceMaintainer

logger = Logger(__file__, 'INFO')
global_config = load_config()

def parse_args():
    parser = argparse.ArgumentParser(description='Run low level experiments for L3/4/5 tasks.')
    parser.add_argument('--instance', type=str, help='Name of the test case instance. Note that only test case in level 3/4/5 can be run here.', required=True)
    parser.add_argument('--suffix', type=str, help='Suffix of the log file.')
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for the agent. Default is 42, use -1 to disable cache seed.')
    return parser.parse_args()

def main(args: argparse.Namespace):
    instance = args.instance
    test_case = load_yaml(os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    
    result_dir = global_config['result_path']
    log_file_path = os.path.join(result_dir, f'{instance}.md' if not args.suffix else f'{instance}-{args.suffix}.md')
    logger.info(f'Start ACV test case {instance}...')

    environment_manager = EnvironmentManager(logger=logger)
    environment_manager.setup(test_case=instance)
    environment_manager.check_pods_ready()

    traffic_loader = TrafficLoader(test_case=instance, logger=logger)
    traffic_loader.start()

    # make sure the cluster is stable
    logger.info(f'Waiting for cluster to be stable, sleeping for 120 seconds...')

    # wait for the cluster to be stable
    time.sleep(120)

    
    if 'chaos' in test_case:
        chaos_factory = ChaosFactory.get_instance()
        chaos_config = test_case['chaos']
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

        time.sleep(60)

    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'],
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
    )

    service_maintainer_consumer = ServiceMaintainerConsumer(
        agent=service_maintainer,
        log_file_path=log_file_path
    )
    service_maintainer_consumer.start()

    logger.warning(f'See log file to get the chat history: {log_file_path}')

    rabbitmq = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
    try:
        for _ in range(3):
            rabbitmq.publish(global_config['heartbeat']['task'], routing_keys=[service_maintainer.name])
            time.sleep(120)

        time.sleep(600)
    except KeyboardInterrupt:
        logger.warning('Experiment interrupted by user')
    traffic_loader.stop()
    
    logger.info(f'Task execution complete.')
    logger.info(f'Stopping ACV test case {instance}...')
    if 'chaos' in test_case:
        chaos_injector.delete_experiment()

    service_maintainer_consumer.stop()
        
    environment_manager.teardown()
    

if __name__ == '__main__':
    args = parse_args()
    main(args)