# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen.coding.func_with_reqs import with_requirements, ImportFromModule
from typing import Literal

def query_prometheus(promQL: str, **kwargs) -> list:
    """
    This function is used to query prometheus with the given promQL.
    - param promQL: str, the promQL to be executed
    - param kwargs: dict, parameters to be passed to the query, must contain one of the following: (start_time, end_time), duration
    
    return: list, result of the query
    
    Available metrics:
    1. request_duration_seconds_count: for query per second (QPS) metric.
    2. request_duration_seconds_bucket: for lantency metric.

    1. name: the service name.
    2. operation: read/write operation.

    Note: ALWAYS call print() to report the result so that planner can get the result.

    Example: 
    >>> from intent_exec.agent.tool_functions_for_maintainer import query_prometheus
    >>> promQL = 'rate(request_duration_seconds_count{name="catalogue"}[1m])'
    >>> result = query_prometheus(promQL=promQL, duration='2m', step='1m')
    >>> print(result) # output the result so that planner can get it.
    [['2024-06-20 02:17:20', 0.0], ['2024-06-20 02:18:20', 0.0], ['2024-06-20 02:19:20', 0.0]]
    """
    from intent_exec.module.prometheus_client import PrometheusClient
    prometheus_client = PrometheusClient()
    result: list[list[str, int]] = prometheus_client.query_range(promQL, **kwargs)
    return result

@with_requirements(python_packages=['Literal'], global_imports=[ImportFromModule('typing', 'Literal')])
def report_result(component: str, message: str, message_type: Literal['ISSUE', 'RESPONSE']) -> str:
    """
    This function can help you send a message to the manager.
    - param component: str, the component name
    - param message: str, the message to be reported
    - param type: str, the type of the message, use 'ISSUE' for HEARTBEAT and 'RESPONSE' for TASK

    return: str, the result of the operation

    Note: ALWAYS call print() to report the result so that planner can get the result.

    Example:
    >>> from intent_exec.agent.tool_functions_for_maintainer import report_result
    >>> component = 'catalogue'
    >>> message = 'The task is completed.'
    >>> message_type = 'RESPONSE'
    >>> result = report_result(component=component, message=messages, message_type=message_type)
    >>> print(result) # output the result so that planner can get it.
    Message sent to manager.
    """
    from intent_exec.module import RabbitMQ, load_config

    global_config = load_config()

    queues = global_config['rabbitmq']['message_collector']['queues']
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['message_collector']['exchange'])
    for queue in queues:
            rabbitmq.add_queue(**queue)

    if message_type == 'ISSUE':
        message = f'ISSUE from component {component}: \n {message}'
    elif message_type == 'RESPONSE':
        message = f'RESPONSE from component {component}: \n {message}'
    else:
        raise ValueError('Invalid message type.')

    rabbitmq.publish(
        message=message,
        routing_keys=['collector'],
        headers={'sender': component}
    )
        
    return 'Message sent to manager.'

# use this list to store all the functions, do not change the name
functions = [query_prometheus, report_result]