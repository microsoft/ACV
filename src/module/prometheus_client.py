# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import traceback
from typing import overload
from datetime import datetime, timedelta
from prometheus_api_client import PrometheusConnect

from .utils import load_config, get_prometheus_url
from .base import Base

global_config = load_config()

class PrometheusClient(Base):

    def __init__(self):
        super().__init__()
        self.prom = self.__connect()

    def __connect(self):
        '''
        Connect to the prometheus instance running in minikube
        '''
        prometheus_url = get_prometheus_url()
        prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        assert prom.check_prometheus_connection(), f"Prometheus connection failed, please check the prometheus url: {prometheus_url}"
        return prom

    def query(self, query: str, params: dict = None):
        '''
        Query the prometheus instance with the given query
        - param query: str, query to be executed
        - param params: dict, parameters to be passed to the query
        - return: list, result of the query
        '''
        result = self.prom.custom_query(query=query, params=params)
        if len(result):
            result = result[0].get('value', None)
        if not result:
            result = []
        else:
            result = [[datetime.fromtimestamp(x[0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(x[1])] for x in result]
        return result
    
    @overload
    def query_range(self, query: str, start_time: str, end_time: str, step: str, time_format: str= r'%Y-%m-%dT%H:%M:%SZ', params = None):
        '''
        Query the prometheus instance with the given query 
        - param query: str, query to be executed
        - param start_time: str, start time of the query, format: time_format
        - param end_time: str, end time of the query, format: time_format
        - param step: str, step of the query, format: 14(s), 1s, 1m, 1h, 1d, 1w
        - param time_format: str, format of the time
        - param params: dict, parameters to be passed to the query
        - return: list, result of the query
        '''
        pass
        
    @overload
    def query_range(self, query: str, duration: str, step: str, params: dict = None):
        '''
        Query the prometheus instance with the given query
        - param query: str, query to be executed
        - param duration: str, duration of the query, format: 1s, 1m, 1h, 1d, 1w
        - param step: str, step of the query, format: 14(s), 1s, 1m, 1h, 1d, 1w
        - param params: list, parameters to be passed to the query
        '''
        pass
        
    @overload
    def query_range(self, query: str, start_time:datetime, end_time:datetime, step: str, params: dict = None):
        '''
        Query the prometheus instance with the given query
        - param query: str, query to be executed
        - param start_time: datetime, start time of the query
        - param end_time: datetime, end time of the query
        - param step: str, step of the query, format: 14(s), 1s, 1m, 1h, 1d, 1w
        - param params: dict, parameters to be passed to the query
        - return: list, result of the query
        '''
        pass
        
    def query_range_by_duration(self, query: str, duration: str, step: str, params: dict = None):
        unit_2time = {
            's': 1,
            'm': 60,
            'h': 60 * 60,
            'd': 60 * 60 * 24,
            'w': 60 * 60 * 7,
        }
        now = datetime.now()
        start_time = now - timedelta(seconds=unit_2time[duration[-1]] * int(duration[:-1]))
        return self.query_range_by_datetime(query=query, start_time=start_time, end_time=now, step=step, params=params)

    def query_range_by_str(self, query: str, start_time: str, end_time: str, step: str, time_format: str = r'%Y-%m-%dT%H:%M:%SZ', params = None):
        try:
            start_time = datetime.strptime(start_time, time_format)
            end_time = datetime.strptime(end_time, time_format)
        except Exception as e:
            self.error(e)
            return None
        return self.query_range_by_datetime(query=query, start_time=start_time, end_time=end_time, step=step, params=params)
    
    def query_range_by_datetime(self, query: str, start_time: datetime, end_time: datetime, step: str, params: dict = None):
        result = self.prom.custom_query_range(query=query, start_time=start_time, end_time=end_time, step=step, params=params)
        if len(result):
            result = result[0].get('values', None)
        if result is None:
            result = []
        else:
            result = [[datetime.fromtimestamp(x[0]).strftime(r'%Y-%m-%d %H:%M:%S'), float(x[1])] for x in result]
        return result
    
    def query_range(self, query: str, **kwargs):
        '''
        function entry, using for query prometheus with variant parameters
        - param query: str, query to be executed
        - param kwargs: dict, parameters to be passed to the query, must contain one of the following: (start_time, end_time), duration
        - return: list, result of the query
        '''
        try:
            if 'params' not in kwargs:
                kwargs['params'] = None
            if 'duration' in kwargs:
                return self.query_range_by_duration(query, kwargs['duration'], kwargs['step'], kwargs['params'])
            elif isinstance(kwargs['start_time'], datetime) and isinstance(kwargs['end_time'], datetime):
                return self.query_range_by_datetime(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], kwargs['params'])
            elif isinstance(kwargs['start_time'], str) and isinstance(kwargs['end_time'], str):
                if 'time_format' not in kwargs:
                    kwargs['time_format'] = r'%Y-%m-%dT%H:%M:%SZ'
                return self.query_range_by_str(query, kwargs['start_time'], kwargs['end_time'], kwargs['step'], kwargs['time_format'], kwargs['params'])
        except:
            self.error(traceback.print_exc())
            return None