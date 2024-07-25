# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import json
import time
import argparse
import traceback
import contextlib

from timeout_decorator import timeout
from opentelemetry import trace
from promptflow.tracing import start_trace
from autogen import UserProxyAgent
from .module import (
    Logger,
    TrafficLoader,
    MetricsCollector,
    EnvironmentManager,
    ChaosFactory,
    ChaosInjector,
    Selector,
    load_config,
    load_yaml
)
from .agent import ServiceMaintainer

logger = Logger(__file__, 'INFO')
global_config = load_config()
time_limit = 360

def parse_args():
    parser = argparse.ArgumentParser(description='Run low level experiments for L1/2 tasks.')
    parser.add_argument('--instance', type=str, help='Name of the test case instance. Note that only test case in level 1/2 can be run here.', required=True)
    parser.add_argument('--suffix', type=str, help='Suffix of the log file.')
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for the agent. Default is 42, use -1 to disable cache seed.')
    return parser.parse_args()

def main(args: argparse.Namespace):
    instance = args.instance
    cache_seed = args.cache_seed if args.cache_seed != -1 else None
    test_case = load_yaml(os.path.join(global_config['dataset']['path'], f'{instance}.yaml'))
    level = test_case['autonomous_level']

    if level > 2:
        logger.error(f'Test case {instance} is not in level 1/2, skip...')
        return
    
    result_dir = global_config['result_path']
    log_file_path = os.path.join(result_dir, f'{instance}.md' if not args.suffix else f'{instance}-{args.suffix}.md')
    logger.info(f'Start ACV test case {instance}...')
    
    # build environment
    environment_manager = EnvironmentManager(logger=logger)
    environment_manager.setup(test_case=instance)

    # make sure the pods are ready
    environment_manager.check_pods_ready()

    # load traffic for the specified duration
    traffic_loader = TrafficLoader(test_case=instance, logger=logger)
    traffic_loader.start()

    # when traffic is ready, start collecting metrics
    metrics_collector = MetricsCollector(test_case=instance, logger=logger)

    # make sure the cluster is stable
    logger.info(f'Waiting for cluster to be stable, checking every 15 seconds...')

    try:
        while True:
            time.sleep(15)
            if metrics_collector.check_stable_state_by_pod(namespace=test_case['namespace'], pod_name=test_case['component']):
                logger.info(f'Cluster is stable now.')
                break
    except KeyboardInterrupt:
        logger.warning(f'Cluster is not stable, task execution interrupted.')
        environment_manager.teardown()
        traffic_loader.stop()
        return

    if 'chaos' in test_case:
        chaos_config = test_case['chaos']
        selector = Selector(**chaos_config['selector'])
        factory = ChaosFactory.get_instance()
        chaos = factory.get_experiment(
            e=chaos_config['type'],
            name=chaos_config['name'],
            namespace=test_case['namespace'],
            selector=selector,
            **chaos_config['args']
        )
        chaos_injector = ChaosInjector(chaos=chaos, logger=logger)
        chaos_injector.start_experiment()

    logger.warning(f'See log file to get the chat history: {log_file_path}')

    with open(log_file_path, 'w') as f:
        with contextlib.redirect_stdout(f):
            try:
                single_agent_task(test_case, cache_seed=cache_seed)
            except KeyboardInterrupt:
                logger.warning(f'Task execution interrupted.')
            except Exception as e:
                logger.error(traceback.print_exc())
                print(traceback.print_exc())

    logger.info(f'Task execute complete.')
    logger.info(f'Stopping ACV test case {instance}...')
    traffic_loader.stop()
    
    if 'chaos' in test_case:
        chaos_injector.delete_experiment()

    environment_manager.teardown()
    
@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def single_agent_task(test_case: dict, cache_seed: int | None = 42):
    '''
    Task execution for single agent
    - param test_case: The test case configuration.
    - param cache_seed: The seed of the cache.
    '''
    start_trace(collection="empicial-single-agent-task")
    tracer = trace.get_tracer("my_tracer")
    # initialize service_maintainer
    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'],
        cache_seed=cache_seed
    )

    user = UserProxyAgent(
        "human",
        human_input_mode="NEVER",
        code_execution_config=False,
        default_auto_reply="",
        is_termination_msg=lambda x: True,
    )

    with tracer.start_as_current_span("autogen") as span:
        # start chat
        user.initiate_chat(service_maintainer, message=test_case['task'])

        span.set_attribute("custom", "custom attribute value")
        span.add_event(
            "promptflow.function.inputs", {"payload": json.dumps(dict(message=test_case['task']))}
        )
        span.add_event(
            "promptflow.function.output", {"payload": json.dumps(user.last_message())}
        )

if __name__ == '__main__':
    args = parse_args()
    main(args)