# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import json
import contextlib
import multiprocessing

from datetime import datetime
from opentelemetry import trace
from promptflow.tracing import start_trace
from autogen import UserProxyAgent, ConversableAgent


from .base import Base
from .utils import load_config
from .message_queue import RabbitMQ

global_config = load_config()

class Consumer(Base):
    def __init__(
        self,
        agent: ConversableAgent,
        log_file_path: str = 'auto',
        **kwargs
    ):
        self.message_queue:RabbitMQ = None
        self.process: multiprocessing.Process = None
        self.agent: ConversableAgent = agent
        self.log_file_path: str = log_file_path
        self.name:str = agent.name

        if log_file_path == 'auto':
            start_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
            result_path = os.path.join(global_config['result_path'], global_config['project']['name'])
            if not os.path.exists(result_path):
                os.makedirs(result_path)

            date_dir = os.path.join(result_path, start_time.split(' ')[0])
            if not os.path.exists(date_dir):
                os.makedirs(date_dir)

            self.log_file_path = os.path.join(date_dir, f'{agent.name}_{start_time}.md')

        self.trigger = UserProxyAgent(
            "trigger",
            human_input_mode="NEVER",
            code_execution_config=False,
            default_auto_reply="",
            is_termination_msg=lambda x: True,
        )

        self.init_message_queue()
        super().__init__(**kwargs)

    def init_message_queue(self):
        raise NotImplementedError("init_message_queue method is not implemented")

    def start(self):
        if self.process:
            self.warning("Consumer is already running.")
            return
        self.process = multiprocessing.Process(target=self.__start_consuming)
        self.process.start()
        # self.info("Consumer started.")

    def stop(self):
        if not self.process:
            self.warning("Consumer is not running.")
            return
        self.process.terminate()
        self.process.join()
        self.process = None
        self.info("Consumer stopped.")

    def chat(self, message: str):
        self.info('Solving task...')
        chat_result = self.trigger.initiate_chat(
            recipient=self.agent,
            clear_history=False,
            message=message
        )
        self.info('*' * 100)
        return chat_result
    
    def callback(self, ch, method, properties, body):
        body = body.decode('utf-8')
        if self.log_file_path:
            with open(self.log_file_path, 'a+') as f:
                with contextlib.redirect_stdout(f):
                    with trace.get_tracer("my_tracer").start_as_current_span("autogen") as span:
                        self.chat(body)
                        span.add_event(
                            "promptflow.function.inputs", {"payload": json.dumps(dict(message=body))}
                        )
                        span.add_event(
                            "promptflow.function.output", {"payload": json.dumps(self.trigger.last_message())}
                        )
        else:
            self.chat(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        # print('Waiting for the next task.')

    def __start_consuming(self):
        try:
            self.message_queue.subscribe(self.name, self.callback)
        except KeyboardInterrupt:
            print("Connection closed.")
            exit(0)

class ManagerConsumer(Consumer):
    def __init__(
        self, 
        agent: ConversableAgent,
        log_file_path: str = 'auto',
    ):
        super().__init__(agent, log_file_path=log_file_path)

    def init_message_queue(self):
        queues = global_config['rabbitmq']['manager']['queues']
        self.message_queue = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
        for queue in queues:
            self.message_queue.add_queue(**queue)
        
    def callback(self, ch, method, properties, body):
        start_trace(collection=f'high-level-{self.name}-{datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")}')
        return super().callback(ch, method, properties, body)
    
class ServiceMaintainerConsumer(Consumer):
    def __init__(
        self, 
        agent: ConversableAgent,
        log_file_path: str = 'auto',
    ):
        super().__init__(agent, log_file_path=log_file_path)

    def init_message_queue(self):
        queues = global_config['rabbitmq']['service_maintainer']['queues']
        self.message_queue = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
        for queue in queues:
            queue['name'] = self.name
            queue['routing_keys'] = [self.name]
            self.message_queue.add_queue(**queue)

    def callback(self, ch, method, properties, body):
        start_trace(collection=f'{self.name}-{datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")}')
        return super().callback(ch, method, properties, body)