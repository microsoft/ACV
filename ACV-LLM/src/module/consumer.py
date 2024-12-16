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
    """
    Base class for managing the lifecycle of a consumer that interacts with a RabbitMQ message queue and an agent.
    """

    def __init__(
        self,
        agent: ConversableAgent,
        log_file_path: str = 'auto',
        **kwargs
    ):
        """
        Initialize the Consumer.

        Parameters:
        - agent (ConversableAgent): The agent to process messages.
        - log_file_path (str): Path to the log file. Default is 'auto', which automatically generates the path.
        - kwargs (dict): Additional arguments passed to the base class.
        """
        self.message_queue: RabbitMQ = None
        self.process: multiprocessing.Process = None
        self.agent: ConversableAgent = agent
        self.log_file_path: str = log_file_path
        self.name: str = agent.name

        if log_file_path == 'auto':
            self._generate_log_file_path()

        self.trigger = UserProxyAgent(
            "trigger",
            human_input_mode="NEVER",
            code_execution_config=False,
            default_auto_reply="",
            is_termination_msg=lambda x: True,
        )

        self.init_message_queue()
        super().__init__(**kwargs)

    def _generate_log_file_path(self):
        """
        Generate the log file path automatically based on the current date and time.
        """
        start_time = datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
        result_path = os.path.join(global_config['result_path'], global_config['project']['name'])
        os.makedirs(result_path, exist_ok=True)

        date_dir = os.path.join(result_path, start_time.split(' ')[0])
        os.makedirs(date_dir, exist_ok=True)

        self.log_file_path = os.path.join(date_dir, f'{self.agent.name}_{start_time}.md')

    def init_message_queue(self):
        """
        Initialize the message queue. This method must be implemented by subclasses.

        Raises:
        - NotImplementedError: If not implemented in a subclass.
        """
        raise NotImplementedError("init_message_queue method is not implemented.")

    def start(self):
        """
        Start the consumer process.
        """
        if self.process:
            self.warning("Consumer is already running.")
            return
        self.process = multiprocessing.Process(target=self.__start_consuming)
        self.process.start()

    def stop(self):
        """
        Stop the consumer process.
        """
        if not self.process:
            self.warning("Consumer is not running.")
            return
        self.process.terminate()
        self.process.join()
        self.process = None
        self.info("Consumer stopped.")

    def chat(self, message: str):
        """
        Send a message to the agent and process the response.

        Parameters:
        - message (str): The message to send to the agent.

        Returns:
        - dict: The agent's response.
        """
        self.info('Solving task...')
        chat_result = self.trigger.initiate_chat(
            recipient=self.agent,
            clear_history=False,
            message=message
        )
        self.info('*' * 100)
        return chat_result

    def callback(self, ch, method, properties, body):
        """
        Process a message from the queue.

        Parameters:
        - ch: The channel.
        - method: The delivery method.
        - properties: The message properties.
        - body: The message body.
        """
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

    def __start_consuming(self):
        """
        Start consuming messages from the queue.
        """
        try:
            self.message_queue.subscribe(self.name, self.callback)
        except KeyboardInterrupt:
            print("Connection closed.")
            exit(0)


class ManagerConsumer(Consumer):
    """
    Consumer class for managing high-level manager messages in RabbitMQ.
    """

    def __init__(self, agent: ConversableAgent, log_file_path: str = 'auto'):
        """
        Initialize the ManagerConsumer.

        Parameters:
        - agent (ConversableAgent): The agent to process messages.
        - log_file_path (str): Path to the log file. Default is 'auto'.
        """
        super().__init__(agent, log_file_path=log_file_path)

    def init_message_queue(self):
        """
        Initialize the message queue for manager messages.
        """
        queues = global_config['rabbitmq']['manager']['queues']
        self.message_queue = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
        for queue in queues:
            self.message_queue.add_queue(**queue)

    def callback(self, ch, method, properties, body):
        """
        Process a manager message from the queue.

        Parameters:
        - ch: The channel.
        - method: The delivery method.
        - properties: The message properties.
        - body: The message body.
        """
        start_trace(collection=f'high-level-{self.name}-{datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")}')
        return super().callback(ch, method, properties, body)


class ServiceMaintainerConsumer(Consumer):
    """
    Consumer class for managing service maintainer messages in RabbitMQ.
    """

    def __init__(self, agent: ConversableAgent, log_file_path: str = 'auto'):
        """
        Initialize the ServiceMaintainerConsumer.

        Parameters:
        - agent (ConversableAgent): The agent to process messages.
        - log_file_path (str): Path to the log file. Default is 'auto'.
        """
        super().__init__(agent, log_file_path=log_file_path)

    def init_message_queue(self):
        """
        Initialize the message queue for service maintainer messages.
        """
        queues = global_config['rabbitmq']['service_maintainer']['queues']
        self.message_queue = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
        for queue in queues:
            queue['name'] = self.name
            queue['routing_keys'] = [self.name]
            self.message_queue.add_queue(**queue)

    def callback(self, ch, method, properties, body):
        """
        Process a service maintainer message from the queue.

        Parameters:
        - ch: The channel.
        - method: The delivery method.
        - properties: The message properties.
        - body: The message body.
        """
        start_trace(collection=f'{self.name}-{datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")}')
        return super().callback(ch, method, properties, body)
