# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
def assign_tasks(components: list, messages: list) -> str:
    """
    This function can help you assign the task to the specific component.
    - param component: the component to which the task is assigned
    - param message: the task message

    return: str, the result of the assignment

    Example:
    >>> from src.agent.tool_functions_for_manager import assign_tasks
    >>> components = ['catalogue', 'front-end']
    >>> messages = ['Please update the service.', 'Please restart the service.']
    >>> result = assign_tasks(components, messages)
    >>> print(result)
    Tasks assigned.
    """
    from intent_exec.module import RabbitMQ, load_config
    from intent_exec.agent.utils import AWAITING_FLAG
    import json
    global_config = load_config()

    assert len(components) == len(messages), 'The number of components and messages should be the same.'
    try:
        queues = global_config['rabbitmq']['message_collector']['queues']
        rabbitmq = RabbitMQ(**global_config['rabbitmq']['message_collector']['exchange'])
        for queue in queues:
            rabbitmq.add_queue(**queue)

        message = json.dumps([components, messages])
        rabbitmq.publish(
            message=message,
            routing_keys=['collector'],
            headers={'sender': 'manager'}
        )
    except Exception as e:
        print(f'Error in assigning task: {e}')
        return 'Tasks assignment failed.'
    return f'Tasks assigned. {AWAITING_FLAG}'

# use this list to store all the functions, do not change the name
functions = [assign_tasks]
