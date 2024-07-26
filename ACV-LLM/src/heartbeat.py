# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import time
import argparse

from .module import (
    RabbitMQ,
    load_config
)

global_config = load_config()

def parse_args():
    parser = argparse.ArgumentParser(description='Heartbeat')
    parser.add_argument('--components', type=str, help='Components to send heartbeat to', required=True)
    parser.add_argument('--total_time', type=int, default=360, help='Total time in seconds to send heartbeat')
    parser.add_argument('--interval', type=int, default=120, help='Interval in seconds')
    return parser.parse_args()

def main(args: argparse.Namespace):
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
    interval = args.interval if args.interval else global_config['heartbeat']['interval']
    components = args.components.split(',') if args.components else global_config['heartbeat']['components']

    count = args.total_time // interval
    print(f"Heartbeat started for {count} times with interval {interval} seconds.")
    try:
        for _ in range(count):
            for component in components:
                rabbitmq.publish(global_config['heartbeat']['task'], routing_keys=[component])
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Heartbeat interrupted by user.")

    print("Heartbeat stopped.")

if __name__ =='__main__':
    args = parse_args()
    main(args)