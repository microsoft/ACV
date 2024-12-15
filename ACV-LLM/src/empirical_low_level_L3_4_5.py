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

logger = Logger(__file__, 'INFO')
global_config = load_config()
time_limit = 360

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

    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(global_config['project']['deployment'], logger=logger)
    environment_manager.setup(config_fpath=os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    environment_manager.check_pods_ready()

    sleep_with_progress(60)

    traffic_loader = TrafficLoader(test_case=instance, logger=logger)
    traffic_loader.start()

    # make sure the cluster is stable
    logger.info(f'Waiting for cluster to be stable, sleeping for 120 seconds...')

    ##########

    # wait for the cluster to be stable
    sleep_with_progress(120)

    InitSLO = checkSLO()
    
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
        traffic_loader_increase = TrafficLoader(test_case="rasing_traffic2", logger=logger)
        traffic_loader_increase.start()
        sleep_with_progress(180)

    AfterInterfrenceSLO = checkSLO()

    agent_framework = global_config['agent']['framework']
    if agent_framework == 'agentscope':
        agentscope_execution(test_case)
    elif agent_framework == 'autogen':
        autogen_execution(test_case, log_file_path)

    ##########

    hash_code = generate_hashcode()

    # Auto evaluate the test case
    evaluator = SockShopEvaluator()
    result = evaluator.evaluate(instance, hash_code)

    # Log the detailed results for each test case
    l3_result = result.get("L3 Assessment", None)
    l4_result = result.get("L4 Assessment", None)
    l5_result = checkSLO()

    stp_cnts = result.get("Step Counts", None)

    # Log the results for each level in a formatted manner
    logger.info(f'Test case {instance} evaluation results:')
    print(f' - L3 (SLO Assessment): {"Passed" if l3_result else "Failed"}')
    print(f' - L4 (Root Cause Identification): {"Passed" if l4_result else "Failed"}')
    print(f' - L5 (Fault Mitigation & Task Delegation): {"Passed" if l5_result else "Failed"}')
    print(f' - Step Counts each Rounds: {stp_cnts}') 

    csv_data = {
        "Id": hash_code,
        "SLO with stable system": InitSLO,
        "SLO with interference": AfterInterfrenceSLO,
        "L3 Assessment": l3_result,
        "L4 Assessment": l4_result,
        "L5 Assessment": l5_result,
        "Step Counts": stp_cnts
    }

    export_csv(csv_data, instance)
    store_chat_history(hash_code)

    traffic_loader.stop()
    
    logger.info(f'Task execution complete.')
    logger.info(f'Stopping ACV test case {instance}...')
    if 'chaos' in test_case:
        chaos_injector.delete_experiment()

    environment_manager.teardown()

@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def agentscope_execution(test_case: dict):
    """
    Task execution for single agent with agentscope framework.

    """
    from multiprocessing import Process
    from .agent.utils import init_agentscope
    init_agentscope()

    from .agent.low_level import ServiceMaintainer
    from agentscope.message import Msg
    from agentscope.pipelines import forlooppipeline

    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'], model_config_name="azure"
    )
    msg = Msg(name='user', content=test_case['task'], role='user', echo=True)

    try:
        for _ in range(3):
            process = Process(target=forlooppipeline, args=([service_maintainer], 1, msg))
            process.start()
            time.sleep(120)

        time.sleep(600)
    except KeyboardInterrupt:
        logger.warning('Experiment interrupted by user')
        process.terminate()


def autogen_execution(test_case: dict, log_file_path: str):
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
            sleep_with_progress(120)

        sleep_with_progress(600)
    except KeyboardInterrupt:
        logger.warning('Experiment interrupted by user')

    service_maintainer_consumer.stop()
    

if __name__ == '__main__':
    args = parse_args()
    main(args)