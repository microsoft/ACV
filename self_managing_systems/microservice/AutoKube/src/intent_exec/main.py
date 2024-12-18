import os
import time
import argparse
import yaml
from datetime import datetime
from .module.utils import get_ancestor_path
from ..api.cloudgpt_aoai import get_chat_completion
from ..self_exploration.main import add_experience

from .module import (
    RabbitMQ,
    Logger,
    load_config, 
    ManagerConsumer,
    ServiceMaintainerConsumer,
    MessageCollector
)
from .agent import (
    ClusterManager,
)
from .agent.service import ServiceMaintainer

logger = Logger(__file__, 'INFO')

global_config = load_config()

base_path = get_ancestor_path(2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Execute the user intent.')
    parser.add_argument('--cache_seed', type=int, default=42, help='Cache seed for agents. Default is 42, use -1 to disable cache seed.')
    parser.add_argument('--intent', type=str, help='Intent name', required=True)

    args = parser.parse_args()
    print(args)

    with open(os.path.join(base_path, 'conf/component_list.yaml'), 'r') as file:
        component_config = yaml.safe_load(file)

    component_list = [component for experiment, components in component_config.items() if experiment != 'common' for component in components]
    component_names = ', '.join({component for experiment in component_config.values() for component in experiment})
    print(f'Available components: {component_list}')

    with open(os.path.join(base_path, 'prompts/component_decomposer.yaml'), 'r') as file:
        prompt_data = yaml.safe_load(file)
        system_prompt = prompt_data['system'].format(component_names=component_names)
        user_prompt = prompt_data['user'].format(intent=args.intent)
        chat_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        engine = "gpt-4-turbo-20240409"
        response = get_chat_completion(engine=engine, messages=chat_messages)
        response_content = response.choices[0].message.content.strip()
        args.components = response_content
        print(f'\033[91m{args.components}\033[0m')

    now_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    result_dir = os.path.join(
        base_path, 
        'results/AutoKube',
        now_time
    )
    os.makedirs(result_dir, exist_ok=True)

    cluster_manager = ClusterManager._init_from_config(
        cache_seed=args.cache_seed if args.cache_seed != -1 else None,
        components=[component.strip() for component in args.components.split(',')]
    )

    manager_consumer = ManagerConsumer(
        agent=cluster_manager,
        log_file_path=os.path.join(result_dir, 'manager.md')
    )
    components = [component.strip() for component in args.components.split(',')]

    if 'global-maintainer' in components:
        components.remove('global-maintainer')

    cluster_name = None
    for cluster, cluster_components in component_config.items():
        if all(component in cluster_components for component in components):
            cluster_name = cluster
            break

    if cluster_name is None:
        raise ValueError("No matching cluster found for the given components")

    print(f'Cluster: {cluster_name}')

    for component in components:
        if component not in component_list:
            raise ValueError(f"Component {component} not found in service maintainers")

    agents = [
        ServiceMaintainer._init_from_config(
            cluster_name=cluster_name,
            service_name=component,
            intent=args.intent,
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
    print(f'\033[91mChat history is also available in the link http://127.0.0.1:23333/v1.0/ui/traces\033[0m')

    queues = global_config['rabbitmq']['manager']['queues']
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
    for queue in queues:
        rabbitmq.add_queue(**queue)
    rabbitmq.publish(f'TASK: {args.intent}', routing_keys=['manager'])

    try:
        time.sleep(600)
    except KeyboardInterrupt:
        logger.warning("Connection closed.")
    finally:
        logger.info(f'Task execute complete.')
        manager_consumer.stop()
        for service_maintainer_consumer in service_maintainer_consumers:
            service_maintainer_consumer.stop()
        message_collector.stop()

    logger.info('Stopping the task...')
    # Output to the terminal the summary of the manager log

    manager_log_path = os.path.join(result_dir, 'manager.md')
    if os.path.exists(manager_log_path):
        with open(manager_log_path, 'r') as file:
            manager_log_content = file.read()
            chat_message = [
                {"role": "system", "content": "Your task is to provide answer of user's intent based on the task description and the chatlog of the process below."},
                {"role": "system", "content": "The output should be the answer of the user's intent! You should check if it works for the user's intent."},
                {"role": "user", "content": "The task description is as follows:"},
                {"role": "user", "content": f"Task: {args.intent}\n"},
                {"role": "user", "content": "The chatlog is as follows, it indicates the process and results of the process:"},
                {"role": "user", "content": manager_log_content}
            ]
            engine = "gpt-4-turbo-20240409"
            response = get_chat_completion(engine=engine, messages=chat_message)
            response_content = response.choices[0].message.content.strip()
            # Output in blue color
            print(f'\033[94m{response_content}\033[0m')
    else:
        logger.warning(f'No manager log file found at {manager_log_path}')
    

    for agent in agents:
        agent_log_path = os.path.join(result_dir, f'{agent.name}.md')
        if os.path.exists(agent_log_path):
            with open(agent_log_path, 'r') as file:
                agent_log_content = file.read()
                add_experience(cluster, agent_log_content)
                logger.info(f'Experience added for agent {agent.name}')
        else:
            logger.warning(f'No log file found for agent {agent.name} at {agent_log_path}')