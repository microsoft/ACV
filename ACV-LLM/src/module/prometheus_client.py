# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import traceback
from typing import overload, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from prometheus_api_client import PrometheusConnect

from .utils import load_config, get_prometheus_url
from .base import Base

global_config = load_config()

class PrometheusClient(Base):
    """
    A client for interacting with a Prometheus instance to execute queries and fetch metrics data.
    """

    def __init__(self):
        """
        Initialize the PrometheusClient and connect to the Prometheus instance.
        """
        super().__init__()
        self.prom = self.__connect()

    def __connect(self) -> PrometheusConnect:
        """
        Establish a connection to the Prometheus instance.

        Returns:
        - PrometheusConnect: An instance of the Prometheus client.

        Raises:
        - AssertionError: If the Prometheus connection fails.
        """
        prometheus_url = get_prometheus_url()
        prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        assert prom.check_prometheus_connection(), f"Prometheus connection failed. Please check the URL: {prometheus_url}"
        return prom

    def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Execute an instant query on the Prometheus instance.

        Args:
        - query (str): The PromQL query to execute.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        result = self.prom.custom_query(query=query, params=params)
        if result and 'value' in result[0]:
            result = [[datetime.fromtimestamp(result[0]['value'][0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(result[0]['value'][1])]]
        else:
            result = []
        return result

    @overload
    def query_range(self, query: str, start_time: str, end_time: str, step: str, time_format: str = r'%Y-%m-%dT%H:%M:%SZ', params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a time range with string-based timestamps.

        Args:
        - query (str): The PromQL query to execute.
        - start_time (str): The start time in the specified format.
        - end_time (str): The end time in the specified format.
        - step (str): The step interval, e.g., '1m', '1h'.
        - time_format (str, optional): The format of the timestamps. Default is ISO 8601.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        ...

    @overload
    def query_range(self, query: str, duration: str, step: str, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a relative time range.

        Args:
        - query (str): The PromQL query to execute.
        - duration (str): The time duration (e.g., '1h', '2d').
        - step (str): The step interval, e.g., '1m', '1h'.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        ...

    @overload
    def query_range(self, query: str, start_time: datetime, end_time: datetime, step: str, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a time range with datetime objects.

        Args:
        - query (str): The PromQL query to execute.
        - start_time (datetime): The start time of the query.
        - end_time (datetime): The end time of the query.
        - step (str): The step interval, e.g., '1m', '1h'.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        ...

    def query_range_by_duration(self, query: str, duration: str, step: str, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a relative time range based on a duration.

        Args:
        - query (str): The PromQL query to execute.
        - duration (str): The time duration (e.g., '1h', '2d').
        - step (str): The step interval, e.g., '1m', '1h'.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        unit_to_seconds = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        now = datetime.now()
        start_time = now - timedelta(seconds=unit_to_seconds[duration[-1]] * int(duration[:-1]))
        return self.query_range_by_datetime(query=query, start_time=start_time, end_time=now, step=step, params=params)

    def query_range_by_str(self, query: str, start_time: str, end_time: str, step: str, time_format: str = r'%Y-%m-%dT%H:%M:%SZ', params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a time range with string-based timestamps.

        Args:
        - query (str): The PromQL query to execute.
        - start_time (str): The start time in the specified format.
        - end_time (str): The end time in the specified format.
        - step (str): The step interval, e.g., '1m', '1h'.
        - time_format (str, optional): The format of the timestamps. Default is ISO 8601.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        try:
            start_time = datetime.strptime(start_time, time_format)
            end_time = datetime.strptime(end_time, time_format)
        except ValueError as e:
            self.error(f"Invalid time format: {e}")
            return []
        return self.query_range_by_datetime(query=query, start_time=start_time, end_time=end_time, step=step, params=params)

    def query_range_by_datetime(self, query: str, start_time: datetime, end_time: datetime, step: str, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Query Prometheus over a time range with datetime objects.

        Args:
        - query (str): The PromQL query to execute.
        - start_time (datetime): The start time of the query.
        - end_time (datetime): The end time of the query.
        - step (str): The step interval, e.g., '1m', '1h'.
        - params (dict, optional): Additional parameters for the query.

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        result = self.prom.custom_query_range(query=query, start_time=start_time, end_time=end_time, step=step, params=params)
        if result and 'values' in result[0]:
            return [[datetime.fromtimestamp(value[0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(value[1])] for value in result[0]['values']]
        return []

    def query_range(self, query: str, **kwargs) -> Optional[list]:
        """
        Main entry for querying Prometheus with variant parameters.

        Args:
        - query (str): The PromQL query to execute.
        - kwargs (dict): Parameters for the query (e.g., start_time, end_time, duration, step).

        Returns:
        - list: The query results as a list of [timestamp, value] pairs.
        """
        try:
            if 'duration' in kwargs:
                return self.query_range_by_duration(query, kwargs['duration'], kwargs['step'], kwargs.get('params'))
            elif isinstance(kwargs.get('start_time'), datetime) and isinstance(kwargs.get('end_time'), datetime):
                return self.query_range_by_datetime(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], kwargs.get('params'))
            elif isinstance(kwargs.get('start_time'), str) and isinstance(kwargs.get('end_time'), str):
                return self.query_range_by_str(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], kwargs.get('time_format', r'%Y-%m-%dT%H:%M:%SZ'), kwargs.get('params'))
        except Exception as e:
            self.error(f"Query execution failed: {e}")
            traceback.print_exc()
        return None
