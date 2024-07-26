# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import pika

from .base import Base
from typing import Literal, Callable

class RabbitMQ(Base):
    def __init__(self,
        exchange_name: str,
        exchange_type: Literal['direct', 'topic', 'headers', 'fanout'] = 'direct',
        **kwargs
    ):
        '''
        Init a RabbitMQ connection with an exchange
        - param exchange_name: str, exchange name
        - param exchange_type: Literal['direct', 'topic', 'headers', 'fanout'], exchange type
        '''
        super().__init__(**kwargs)
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        connection_params = pika.ConnectionParameters(
            host='localhost',
            heartbeat=180,  # Set heartbeat interval to 10 minutes
        )
        self.connection = pika.BlockingConnection(connection_params)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=self.exchange_name, exchange_type=self.exchange_type)

    def add_queue(self, name: str, routing_keys: list[str], exclusive: bool = False, auto_delete: bool = False):
        '''
        Add a queue with routing keys to the exchange
        - param name: str, queue name
        - param routing_keys: list[str], list of routing keys
        - param exclusive: bool, exclusive queue
        - param auto_delete: bool, auto delete queue
        '''
        self.channel.queue_declare(queue=name, durable=True, exclusive=exclusive, auto_delete=auto_delete)
        for routing_key in routing_keys:
            self.channel.queue_bind(
                exchange=self.exchange_name, 
                queue=name, 
                routing_key=routing_key
            )

    def publish(self, message: str, routing_keys: list[str], headers: dict = {}):
        '''
        Add a message to the exchange with routing keys
        - param message: str, message
        - param routing_keys: list[str], list of routing keys
        '''
        properties = pika.BasicProperties(
            delivery_mode=2,
            headers=headers
        )
        for routing_key in routing_keys:
            self.channel.basic_publish(
                exchange=self.exchange_name, 
                routing_key=routing_key, 
                body=message,
                properties=properties
            )
        # self.info(f"Published message: {message} to {self.exchange_name} with routing key: {routing_key}")

    def subscribe(self, queue: str, callback: Callable, auto_ack: bool = False):
        '''
        Subscribe to a queue and start consuming with a callback function, this function will block the main process
        - param queue: str, queue name
        - param callback: Callable, callback function
        - param auto_ack: bool, auto acknowledge
        '''
        self.channel.basic_consume(queue=queue, on_message_callback=callback, auto_ack=auto_ack)
        self.info(f"Subscribed to queue: {queue}")
        self.channel.start_consuming()
    
    def close(self):
        if self.connection:
            self.connection.close()