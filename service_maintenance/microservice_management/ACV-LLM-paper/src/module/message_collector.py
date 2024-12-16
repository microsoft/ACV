# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import multiprocessing
from collections import defaultdict
from .message_queue import RabbitMQ
from .utils import load_config
from .base import Base

# Load global configuration
global_config = load_config()

class MessageCollector(Base):
    """
    MessageCollector is responsible for collecting messages from the message queue,
    distributing tasks to service maintainers, and consolidating responses.

    Attributes:
    - round (int): The current round of message collection.
    - process (multiprocessing.Process): The background process for collecting messages.
    - message_count (int): The count of messages to be processed in the current round.
    - message_dict (dict): A dictionary mapping components to their messages.
    - rabbitmq (RabbitMQ): RabbitMQ instance for interacting with message queues.
    """

    def __init__(self, **kwargs):
        """
        Initialize the MessageCollector.

        Args:
        - kwargs: Additional arguments for the Base class.
        """
        super().__init__(**kwargs)
        self.round: int = 0
        self.process: multiprocessing.Process = None
        self.message_count: int = 0
        self.message_dict: dict[str, str] = defaultdict(str)
        self.rabbitmq = RabbitMQ(**global_config['rabbitmq']['message_collector']['exchange'])
        queues = global_config['rabbitmq']['message_collector']['queues']
        for queue in queues:
            self.rabbitmq.add_queue(**queue)

    def start(self):
        """
        Start the MessageCollector in a separate process.
        """
        if self.process:
            self.warning("MessageCollector is already running.")
            return
        self.process = multiprocessing.Process(target=self.__collect)
        self.process.start()
        self.info("MessageCollector started.")

    def stop(self):
        """
        Stop the MessageCollector process.
        """
        if not self.process:
            self.warning("MessageCollector is not running.")
            return
        self.process.terminate()
        self.process.join()
        self.process = None
        self.info("MessageCollector stopped.")

    def __collect(self):
        """
        Collect messages from the RabbitMQ queue and process them.

        Messages are classified as:
        - Manager messages: Increment the round and distribute tasks to components.
        - Component responses: Collect responses and send them back to the manager.
        """

        def callback(channel, method, properties, body):
            sender = properties.headers.get('sender')
            body = body.decode('utf-8')
            if sender == 'manager':
                self.round += 1
                # Message contains a list of components and their respective messages
                information = json.loads(body)
                components, messages = information[0], information[1]
                self.assign_tasks(components, messages)
            else:
                self.response(sender, body)
            channel.basic_ack(delivery_tag=method.delivery_tag)

        try:
            self.rabbitmq.subscribe(queue='collector', callback=callback)
        except KeyboardInterrupt:
            self.warning("Connection closed.")
            exit(0)

    def assign_tasks(self, components: list[str], messages: list[str]):
        """
        Distribute tasks to the specified components.

        Args:
        - components (list[str]): List of component names.
        - messages (list[str]): Corresponding messages for each component.
        """
        self.message_count = len(messages)
        self.message_dict.clear()

        # Publish tasks to the service maintainers
        project_rabbitmq = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
        for component, message in zip(components, messages):
            project_rabbitmq.publish(
                message=message,
                routing_keys=[component]
            )

    def response(self, component: str, message: str):
        """
        Handle responses from components and send aggregated response to the manager.

        Args:
        - component (str): The component sending the response.
        - message (str): The response message from the component.
        """
        self.message_count -= 1
        self.message_dict[component] = message

        if self.message_count == 0:
            # Aggregate responses and send to the manager
            response_message = "\n".join(self.message_dict.values())
            project_rabbitmq = RabbitMQ(**global_config['rabbitmq']['manager']['exchange'])
            queues = global_config['rabbitmq']['manager']['queues']
            for queue in queues:
                project_rabbitmq.add_queue(**queue)

            project_rabbitmq.publish(
                message=response_message,
                routing_keys=['manager'],
            )
