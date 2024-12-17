# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import traceback
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from prometheus_api_client import PrometheusConnect

class PrometheusClient:
    """
    A client for querying Prometheus metrics using the Prometheus API.
    """

    def __init__(self):
        """
        Initialize the Prometheus client and connect to the Prometheus instance.
        """
        self.prom = self.__connect()

    def __connect(self) -> PrometheusConnect:
        """
        Connect to the Prometheus instance.

        Returns:
        - PrometheusConnect: An instance of the Prometheus connection.

        Raises:
        - AssertionError: If the connection to Prometheus fails.
        """
        prometheus_url = "http://localhost:9090"
        prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        assert prom.check_prometheus_connection(), (
            f"Prometheus connection failed. Please check the URL: {prometheus_url}"
        )
        return prom

    def query(self, query: str, params: Optional[Dict] = None) -> List:
        """
        Execute a Prometheus query.

        Parameters:
        - query (str): The PromQL query string.
        - params (Optional[Dict]): Additional query parameters.

        Returns:
        - List: Query results in the form of timestamps and values.
        """
        result = self.prom.custom_query(query=query, params=params)
        if result:
            values = result[0].get('value', None)
            if values:
                return [[datetime.fromtimestamp(values[0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(values[1])]]
        return []

    def query_range_by_duration(self, query: str, duration: str, step: str, params: Optional[Dict] = None) -> List:
        """
        Query Prometheus over a duration.

        Parameters:
        - query (str): The PromQL query string.
        - duration (str): Duration of the query (e.g., '1h', '2d').
        - step (str): Query step (e.g., '15s', '1m').
        - params (Optional[Dict]): Additional query parameters.

        Returns:
        - List: Query results in the form of timestamps and values.
        """
        unit_to_seconds = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        now = datetime.now()
        duration_seconds = unit_to_seconds[duration[-1]] * int(duration[:-1])
        start_time = now - timedelta(seconds=duration_seconds)
        return self.query_range_by_datetime(query, start_time, now, step, params)

    def query_range_by_str(self, query: str, start_time: str, end_time: str, step: str, 
                           time_format: str = r'%Y-%m-%dT%H:%M:%SZ', params: Optional[Dict] = None) -> List:
        """
        Query Prometheus over a time range defined by string timestamps.

        Parameters:
        - query (str): The PromQL query string.
        - start_time (str): Start time in string format.
        - end_time (str): End time in string format.
        - step (str): Query step (e.g., '15s', '1m').
        - time_format (str): Format of the string timestamps. Default is ISO format.
        - params (Optional[Dict]): Additional query parameters.

        Returns:
        - List: Query results in the form of timestamps and values.

        Raises:
        - ValueError: If the timestamps cannot be parsed.
        """
        try:
            start_time = datetime.strptime(start_time, time_format)
            end_time = datetime.strptime(end_time, time_format)
        except ValueError as e:
            self.error(f"Invalid time format: {e}")
            return []
        return self.query_range_by_datetime(query, start_time, end_time, step, params)

    def query_range_by_datetime(self, query: str, start_time: datetime, end_time: datetime, 
                                step: str, params: Optional[Dict] = None) -> List:
        """
        Query Prometheus over a time range defined by datetime objects.

        Parameters:
        - query (str): The PromQL query string.
        - start_time (datetime): Start time of the query.
        - end_time (datetime): End time of the query.
        - step (str): Query step (e.g., '15s', '1m').
        - params (Optional[Dict]): Additional query parameters.

        Returns:
        - List: Query results in the form of timestamps and values.
        """
        result = self.prom.custom_query_range(
            query=query, start_time=start_time, end_time=end_time, step=step, params=params
        )
        if result:
            values = result[0].get('values', None)
            if values:
                return [[datetime.fromtimestamp(x[0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(x[1])] for x in values]
        return []

    def query_range(self, query: str, **kwargs) -> List:
        """
        Query Prometheus with flexible parameters.

        Parameters:
        - query (str): The PromQL query string.
        - kwargs (dict): Additional query parameters, including:
            - 'start_time' (str/datetime): Start time of the query.
            - 'end_time' (str/datetime): End time of the query.
            - 'duration' (str): Duration of the query (e.g., '1h').
            - 'step' (str): Query step (e.g., '15s').
            - 'params' (dict): Additional query parameters.

        Returns:
        - List: Query results in the form of timestamps and values.
        """
        try:
            if 'duration' in kwargs:
                return self.query_range_by_duration(query, kwargs['duration'], kwargs['step'], kwargs.get('params'))
            if 'start_time' in kwargs and 'end_time' in kwargs:
                if isinstance(kwargs['start_time'], datetime) and isinstance(kwargs['end_time'], datetime):
                    return self.query_range_by_datetime(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], kwargs.get('params'))
                elif isinstance(kwargs['start_time'], str) and isinstance(kwargs['end_time'], str):
                    time_format = kwargs.get('time_format', r'%Y-%m-%dT%H:%M:%SZ')
                    return self.query_range_by_str(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], time_format, kwargs.get('params'))
        except Exception as e:
            self.error(f"Query failed: {traceback.format_exc()}")
        return []
