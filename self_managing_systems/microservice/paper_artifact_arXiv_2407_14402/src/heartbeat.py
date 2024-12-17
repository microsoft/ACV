# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import time
import argparse

from .module import (
    RabbitMQ,
    load_config
)

# Load global configuration
global_config = load_config()

def parse_args():
    """
    Parse command-line arguments for the heartbeat script.

    Returns:
    - argparse.Namespace: Parsed arguments including components, total_time, and interval.
    """
    parser = argparse.ArgumentParser(description='Heartbeat Script')
    parser.add_argument(
        '--components', type=str, required=True,
        help='Comma-separated list of components to send heartbeat messages to.'
    )
    parser.add_argument(
        '--total_time', type=int, default=360,
        help='Total duration (in seconds) to send heartbeat messages. Default is 360 seconds.'
    )
    parser.add_argument(
        '--interval', type=int, default=120,
        help='Time interval (in seconds) between heartbeat messages. Default is 120 seconds.'
    )
    return parser.parse_args()

def main(args: argparse.Namespace):
    """
    Main function to send heartbeat messages to specified components.

    Parameters:
    - args (argparse.Namespace): Parsed command-line arguments.
    """
    # Initialize RabbitMQ instance with configuration
    rabbitmq = RabbitMQ(**global_config['rabbitmq']['service_maintainer']['exchange'])
    
    # Use the specified interval or default from configuration
    interval = args.interval if args.interval else global_config['heartbeat']['interval']
    
    # Parse the list of components
    components = args.components.split(',') if args.components else global_config['heartbeat']['components']
    
    # Calculate the number of heartbeat cycles
    count = args.total_time // interval
    print(f"Heartbeat started for {count} cycles with an interval of {interval} seconds.")

    try:
        for _ in range(count):
            for component in components:
                # Send heartbeat message to each component
                rabbitmq.publish(global_config['heartbeat']['task'], routing_keys=[component])
            time.sleep(interval)  # Wait for the specified interval before the next cycle
    except KeyboardInterrupt:
        print("Heartbeat interrupted by user.")

    print("Heartbeat stopped.")

if __name__ == '__main__':
    args = parse_args()
    main(args)
