# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import pika
from .base import Base
from typing import Literal, Callable

class RabbitMQ(Base):
    """
    RabbitMQ class provides functionalities for connecting to a RabbitMQ server,
    declaring exchanges and queues, publishing messages, and subscribing to queues.
    """

    def __init__(
        self,
        exchange_name: str,
        exchange_type: Literal['direct', 'topic', 'headers', 'fanout'] = 'direct',
        **kwargs
    ):
        """
        Initialize a RabbitMQ connection and declare an exchange.

        Args:
        - exchange_name (str): Name of the RabbitMQ exchange.
        - exchange_type (Literal['direct', 'topic', 'headers', 'fanout'], optional): Type of the exchange. Default is 'direct'.
        - kwargs (dict): Additional arguments for the Base class.
        """
        super().__init__(**kwargs)
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type

        # Set up connection parameters
        connection_params = pika.ConnectionParameters(
            host='localhost',  # RabbitMQ server host
            heartbeat=180,  # Heartbeat interval in seconds
        )
        # Establish connection and channel
        self.connection = pika.BlockingConnection(connection_params)
        self.channel = self.connection.channel()
        # Declare exchange
        self.channel.exchange_declare(
            exchange=self.exchange_name, 
            exchange_type=self.exchange_type
        )

    def add_queue(self, name: str, routing_keys: list[str], exclusive: bool = False, auto_delete: bool = False):
        """
        Declare a queue and bind it to the exchange using the provided routing keys.

        Args:
        - name (str): Name of the queue.
        - routing_keys (list[str]): List of routing keys for binding the queue.
        - exclusive (bool, optional): Whether the queue is exclusive to the connection. Default is False.
        - auto_delete (bool, optional): Whether the queue should auto-delete when not in use. Default is False.
        """
        self.channel.queue_declare(
            queue=name, 
            durable=True, 
            exclusive=exclusive, 
            auto_delete=auto_delete
        )
        # Bind the queue to the exchange with each routing key
        for routing_key in routing_keys:
            self.channel.queue_bind(
                exchange=self.exchange_name, 
                queue=name, 
                routing_key=routing_key
            )

    def publish(self, message: str, routing_keys: list[str], headers: dict = {}):
        """
        Publish a message to the exchange with the specified routing keys.

        Args:
        - message (str): The message to be published.
        - routing_keys (list[str]): List of routing keys for publishing the message.
        - headers (dict, optional): Additional headers to include with the message. Default is an empty dictionary.
        """
        properties = pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
            headers=headers
        )
        for routing_key in routing_keys:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=message,
                properties=properties
            )
        # self.info(f"Published message: {message} to {self.exchange_name} with routing keys: {routing_keys}")

    def subscribe(self, queue: str, callback: Callable, auto_ack: bool = False):
        """
        Subscribe to a queue and start consuming messages with a callback function.

        Args:
        - queue (str): Name of the queue to subscribe to.
        - callback (Callable): Callback function to process messages.
        - auto_ack (bool, optional): Whether to auto-acknowledge messages. Default is False.
        """
        self.channel.basic_consume(
            queue=queue, 
            on_message_callback=callback, 
            auto_ack=auto_ack
        )
        self.info(f"Subscribed to queue: {queue}")
        self.channel.start_consuming()

    def close(self):
        """
        Close the RabbitMQ connection.
        """
        if self.connection:
            self.connection.close()
