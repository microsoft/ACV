# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import json
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
    EnvironmentManagerFactory,
    ServiceMaintainerConsumer
)
from .agent import ServiceMaintainer
from timeout_decorator import timeout
from .evaluate.sock_shop_evaluator import SockShopEvaluator
from .evaluate.slo_checker import checkSLO
from .util_tools import sleep_with_progress, export_csv, generate_hashcode, store_chat_history

# Initialize logger and global configuration
logger = Logger(__file__, 'INFO')
global_config = load_config()

# Time limit for execution
time_limit = 360

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including instance, suffix, and cache seed.
    """
    parser = argparse.ArgumentParser(description='Run low-level experiments for L3/4/5 tasks.')
    parser.add_argument(
        '--instance', type=str, required=True,
        help='Name of the test case instance. Only test cases in level 3/4/5 can be run here.'
    )
    parser.add_argument(
        '--suffix', type=str,
        help='Suffix of the log file.'
    )
    parser.add_argument(
        '--cache_seed', type=int, default=42,
        help='Cache seed for the agent. Default is 42, use -1 to disable cache seed.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to execute the specified test case.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    instance = args.instance
    test_case = load_yaml(os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    
    result_dir = global_config['result_path']
    log_file_path = os.path.join(result_dir, f'{instance}.md' if not args.suffix else f'{instance}-{args.suffix}.md')
    logger.info(f'Starting ACV test case {instance}...')

    # Set up the environment
    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(
        global_config['project']['deployment'], logger=logger
    )
    environment_manager.setup(config_fpath=os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    environment_manager.check_pods_ready()

    sleep_with_progress(60)

    # Start traffic loader
    traffic_loader = TrafficLoader(test_case=instance, logger=logger)
    traffic_loader.start()

    # Ensure cluster stability
    logger.info('Waiting for cluster stability (120 seconds)...')
    sleep_with_progress(120)

    InitSLO = checkSLO()

    # Inject chaos or increase traffic based on the test case
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
        sleep_with_progress(120)
    else:
        traffic_loader.stop()
        traffic_loader_increase = TrafficLoader(test_case="raising_traffic2", logger=logger)
        traffic_loader_increase.start()
        sleep_with_progress(180)

    AfterInterferenceSLO = checkSLO()

    # Execute based on the agent framework
    agent_framework = global_config['agent']['framework']
    if agent_framework == 'agentscope':
        agentscope_execution(test_case)
    elif agent_framework == 'autogen':
        autogen_execution(test_case, log_file_path)

    # Evaluate the test case
    hash_code = generate_hashcode()
    evaluator = SockShopEvaluator()
    result = evaluator.evaluate(instance, hash_code)

    # Log detailed results
    l3_result = result.get("L3 Assessment", None)
    l4_result = result.get("L4 Assessment", None)
    l5_result = checkSLO()
    step_counts = result.get("Step Counts", None)

    logger.info(f'Test case {instance} evaluation results:')
    print(f' - L3 (SLO Assessment): {"Passed" if l3_result else "Failed"}')
    print(f' - L4 (Root Cause Identification): {"Passed" if l4_result else "Failed"}')
    print(f' - L5 (Fault Mitigation & Task Delegation): {"Passed" if l5_result else "Failed"}')
    print(f' - Step Counts each Round: {step_counts}') 

    # Export results to CSV
    csv_data = {
        "Id": hash_code,
        "SLO with stable system": InitSLO,
        "SLO with interference": AfterInterferenceSLO,
        "L3 Assessment": l3_result,
        "L4 Assessment": l4_result,
        "L5 Assessment": l5_result,
        "Step Counts": step_counts
    }
    export_csv(csv_data, instance)
    store_chat_history(hash_code)

    traffic_loader.stop()
    
    logger.info('Task execution complete.')
    logger.info(f'Stopping ACV test case {instance}...')
    if 'chaos' in test_case:
        chaos_injector.delete_experiment()

    environment_manager.teardown()

@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def agentscope_execution(test_case: dict):
    """
    Task execution for a single agent using the AgentScope framework.

    Parameters:
    - test_case (dict): Configuration dictionary for the test case.
    """
    from multiprocessing import Process
    from .agent.utils import init_agentscope
    from .agent.low_level import ServiceMaintainer
    from agentscope.message import Msg
    from agentscope.pipelines import forlooppipeline

    init_agentscope()
    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'], model_config_name="azure"
    )
    msg = Msg(name='user', content=test_case['task'], role='user', echo=True)

    try:
        for _ in range(3):
            process = Process(target=forlooppipeline, args=([service_maintainer], 1, msg))
            process.start()
            time.sleep(120)
    except KeyboardInterrupt:
        logger.warning('Experiment interrupted by user')
        process.terminate()

def autogen_execution(test_case: dict, log_file_path: str):
    """
    Task execution for a single agent using the Autogen framework.

    Parameters:
    - test_case (dict): The test case configuration.
    - log_file_path (str): Path to log file for chat history.
    """
    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'],
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
    )

    service_maintainer_consumer = ServiceMaintainerConsumer(
        agent=service_maintainer,
        log_file_path=log_file_path
    )
    service_maintainer_consumer.start()

    logger.warning(f'See log file for chat history: {log_file_path}')

    rabbitmq = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
    try:
        for _ in range(3):
            rabbitmq.publish(global_config['heartbeat']['task'], routing_keys=[service_maintainer.name])
            sleep_with_progress(120)
    except KeyboardInterrupt:
        logger.warning('Experiment interrupted by user')

    service_maintainer_consumer.stop()

if __name__ == '__main__':
    args = parse_args()
    main(args)
