# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import json
import time
import argparse
import traceback
import contextlib

from autogen.agentchat.chat import ChatResult
from timeout_decorator import timeout
from opentelemetry import trace
from .module import (
    Logger,
    TrafficLoader,
    EnvironmentManagerFactory,
    ChaosFactory,
    ChaosInjector,
    Selector,
    load_config,
    load_yaml
)
from .evaluate.sock_shop_evaluator import SockShopEvaluator
from .util_tools import generate_hashcode

# Initialize logger and global configuration
logger = Logger(__file__, 'INFO')
global_config = load_config()

# Time limit for task execution
time_limit = 360

def parse_args():
    """
    Parse command-line arguments for the script.

    Returns:
    - argparse.Namespace: Parsed arguments including instance, suffix, and cache seed.
    """
    parser = argparse.ArgumentParser(description='Run low-level experiments for L1/2 tasks.')
    parser.add_argument(
        '--instance', type=str, required=True,
        help='Name of the test case instance. Only test cases in level 1/2 can be run here.'
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
    cache_seed = args.cache_seed if args.cache_seed != -1 else None

    # Load the test case configuration
    test_case = load_yaml(
        os.path.join(global_config['dataset']['path'], f'{instance}.yaml')
    )
    level = test_case['autonomous_level']

    if level > 2:
        logger.error(f'Test case {instance} is not in level 1/2, skipping...')
        return
    
    result_dir = global_config['result_path']
    log_file_path = os.path.join(
        result_dir, 
        global_config['project']['name'], 
        f'{instance}.md' if not args.suffix else f'{instance}-{args.suffix}.md'
    )
    chat_history_path = os.path.join(
        result_dir,
        global_config['project']['name'],
        'structuralized_history',
        f'{instance}.json' if not args.suffix else f'{instance}-{args.suffix}.json'
    )
    logger.info(f'Starting ACV test case {instance}...')

    # Set up the environment
    environment_manager_factory = EnvironmentManagerFactory.get_instance()
    environment_manager = environment_manager_factory.get_environment(
        global_config['project']['deployment'], logger=logger
    )
    environment_manager.setup(
        config_fpath=os.path.join(global_config['dataset']['path'], f'{instance}.yaml')
    )
    environment_manager.check_pods_ready()

    # Start traffic loader
    traffic_loader = TrafficLoader(test_case=instance, logger=logger)
    traffic_loader.start()

    # Wait for the cluster to stabilize
    logger.info('Waiting for cluster stability (120 seconds)...')
    time.sleep(120)

    # Inject chaos if specified in the test case
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

    logger.warning(f'Check log file for chat history: {log_file_path}')

    # Execute the task and capture logs
    with open(log_file_path, 'w') as f:
        with contextlib.redirect_stdout(f):
            try:
                agent_framework = global_config['agent']['framework']
                if agent_framework == 'agentscope':
                    agentscope_execution(test_case)
                elif agent_framework == 'autogen':
                    autogen_execution(test_case, chat_history_path, cache_seed)
                else:
                    raise ValueError(f'Invalid agent framework: {agent_framework}')
            except KeyboardInterrupt:
                logger.warning('Task execution interrupted.')
            except Exception as e:
                logger.error(traceback.print_exc())
                print(traceback.print_exc())

    # Evaluate the test case
    hash_code = generate_hashcode()
    evaluator = SockShopEvaluator()
    result = evaluator.evaluate(instance, hash_code)
    logger.info(f'Test case {instance} evaluation result: {result}')

    logger.info('Task execution complete.')
    logger.info(f'Stopping ACV test case {instance}...')
    traffic_loader.stop()

    if 'chaos' in test_case:
        chaos_injector.delete_experiment()

    environment_manager.teardown()

@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def agentscope_execution(test_case: dict):
    """
    Execute the task using the AgentScope framework.

    Parameters:
    - test_case (dict): Configuration dictionary for the test case.
    """
    from .agent.utils import init_agentscope
    from .agent.low_level import ServiceMaintainer
    from agentscope.message import Msg
    from agentscope.pipelines import forlooppipeline

    init_agentscope()
    service_maintainer = ServiceMaintainer._init_from_config(
        service_name=test_case['component'], model_config_name="azure"
    )
    msg = Msg(name='user', content=test_case['task'], role='user', echo=True)

    forlooppipeline(loop_body_operators=[service_maintainer], max_loop=1, x=msg)

@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def autogen_execution(test_case: dict, chat_history_path: str, cache_seed: int | None = 42):
    """
    Execute the task using the Autogen framework.

    Parameters:
    - test_case (dict): The test case configuration.
    - chat_history_path (str): The path to store chat history.
    - cache_seed (int | None): Cache seed for agents. Default is 42.
    """
    from .agent.service import ServiceMaintainer
    from autogen import UserProxyAgent

    tracer = trace.get_tracer("my_tracer")

    # Initialize service maintainer
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
        chat_history: ChatResult = user.initiate_chat(service_maintainer, message=test_case['task'])
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
