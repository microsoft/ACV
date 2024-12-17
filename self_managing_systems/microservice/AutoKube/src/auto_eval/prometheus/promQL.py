# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

def query_prometheus(promQL: str, **kwargs) -> list:
    """
    This function is used to query prometheus with the given promQL.
    - param promQL: str, the promQL to be executed
    - param kwargs: dict, parameters to be passed to the query, must contain one of the following: (start_time, end_time), duration
    
    return: list, result of the query
    
    Available metrics:
    1. request_duration_seconds_count: for query per second (QPS) metric.
    2. request_duration_seconds_bucket: for lantency metric.
    Available filters:
    1. name: the service name.
    2. operation: read/write operation.

    Note: ALWAYS call print() to report the result so that planner can get the result.

    Example: 
    >>> from src.agent.tool_functions_for_maintainer import query_prometheus
    >>> promQL = 'rate(request_duration_seconds_count{name="catalogue"}[1m])'
    >>> result = query_prometheus(promQL=promQL, duration='2m', step='1m')
    >>> print(result) # output the result so that planner can get it.
    [['2024-06-20 02:17:20', 0.0], ['2024-06-20 02:18:20', 0.0], ['2024-06-20 02:19:20', 0.0]]
    """
    from .prometheus_client import PrometheusClient
    prometheus_client = PrometheusClient()
    result: list[list[str, int]] = prometheus_client.query_range(promQL, **kwargs)
    return result