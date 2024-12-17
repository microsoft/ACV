import os
import time
import argparse
import traceback
import json
import random
from timeout_decorator import timeout
from opentelemetry import trace
import contextlib
from autogen.agentchat.chat import ChatResult
from .module.utils import get_ancestor_path
from ..api.cloudgpt_aoai import get_chat_completion

from .module import (
    RabbitMQ,
    Logger,
    load_config, 
    load_yaml,
    ManagerConsumer,
    ServiceMaintainerConsumer,
    MessageCollector
)
from .agent import (
    ClusterManager,
)
from .agent.service import ServiceMaintainer

from ..auto_eval.main import Evaluator

logger = Logger(__file__, 'INFO')

global_config = load_config()

base_path = get_ancestor_path(2)

time_limit = 360

@timeout(time_limit, timeout_exception=Exception, exception_message=f'Timeout after {time_limit} seconds.')
def autogen_execution(experiment: str, test_case: dict, chat_history_path: str, cache_seed: int | None = 42):
    '''
    Task execution for single agent
    - param test_case: The test case configuration.
    - param chat_history_path: The path to store the chat history.
    - param cache_seed: The seed of the cache.
    '''
    from .agent.service import ServiceMaintainer
    from autogen import UserProxyAgent

    # start_trace(collection="empicial-single-agent-task")
    tracer = trace.get_tracer("my_tracer")
    # initialize service_maintainer
    service_maintainer = ServiceMaintainer._init_from_config(
        cluster_name=experiment,
        service_name=test_case['component'],
        intent="",
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
        chat_history: ChatResult = user.initiate_chat(service_maintainer, message=test_case['task'])

        # json.dump(chat_history, open(chat_history_path, "w"))

        span.set_attribute("custom", "custom attribute value")
        span.add_event(
            "promptflow.function.inputs", {"payload": json.dumps(dict(message=test_case['task']))}
        )
        span.add_event(
            "promptflow.function.output", {"payload": json.dumps(user.last_message())}
        )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Execute the user intent.')
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for agents. Default is 42, use -1 to disable cache seed.')
    parser.add_argument('--instance', type=str, help='Instance name', required=True)
    parser.add_argument('--experiment', type=str, help='Experiment name', required=True)

    args = parser.parse_args()
    print(args)

    args.cache_seed = random.randint(0, 1000)

    test_case = load_yaml(
        os.path.join(base_path, 'dataset', f'{args.experiment}/{args.instance}.yaml')
    )
    result_dir = os.path.join(
        base_path, 
        'results/Experiment'
    )
    os.makedirs(result_dir, exist_ok=True)
    log_file_path = os.path.join(
        result_dir, 
        args.experiment, 
        f'{args.instance}.md'
    )
    chat_history_path = os.path.join(
        result_dir, 
        args.experiment, 
        'structuralized_history',
        f'{args.instance}.json'
    )
    logger.info(f'Start ACV test case {args.instance}...')
    while True:
        user_input = input("You have set up the environment? (yes/no): ").strip().lower()
        if user_input == 'yes':
            # Add your logic to add traffic to the specific pods here
            break
        elif user_input == 'no':
            continue
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    while True:
        user_input = input("You have add traffic to specific service? (yes/no): ").strip().lower()
        if user_input == 'yes':
            # Add your logic to add traffic to the specific pods here
            break
        elif user_input == 'no':
            continue
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    logger.info(f'Waiting for cluster to be stable, sleeping for 60 seconds...')
    # time.sleep(60)
    
    while True:
        user_input = input("You have add chaos to specific service? (yes/no): ").strip().lower()
        if user_input == 'yes':
            # Add your logic to add traffic to the specific pods here
            break
        elif user_input == 'no':
            continue
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")
    
    logger.info(f'Waiting for cluster to be stable, sleeping for 120 seconds...')
    # time.sleep(120)

    logger.warning(f'See log file to get the chat history: {log_file_path}')
    with open(log_file_path, 'w') as f:
        with contextlib.redirect_stdout(f):
            try:
                autogen_execution(args.experiment, test_case, chat_history_path, args.cache_seed)
            except KeyboardInterrupt:
                logger.warning(f'Task execution interrupted.')
            except Exception as e:
                logger.error(traceback.print_exc())
                print(traceback.print_exc())

    logger.info(f'Task execute complete.')
    evaluator = Evaluator(args.instance, args.experiment, test_case['component'])
    result = evaluator.callEvaluator()
    print(result)
    logger.info(f'Stopping ACV test case {args.instance}...')

    history_results_dir = os.path.join(result_dir, 'history_results')
    os.makedirs(history_results_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    new_log_file_path = os.path.join(history_results_dir, f'{timestamp}.md')
    os.rename(log_file_path, new_log_file_path)
    logger.info(f'Log file moved to: {new_log_file_path}')