# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from ..utils.logger import Logger
from .agent_creation import agent_creation, agent_deprecated

logger = Logger(__file__, 'INFO')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Experiment Setup Module')
    parser.add_argument('--namespace', type=str, help='Namespace', default='sock-shop')
    parser.add_argument('--setup', action='store_true', help='Setup the namespace')

    args = parser.parse_args()

    print(args)
    if args.setup:
        agent_creation(args.namespace)
    else:
        agent_deprecated(args.namespace)
