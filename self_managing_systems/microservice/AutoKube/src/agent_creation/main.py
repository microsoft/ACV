import argparse
from ..utils.logger import Logger
from .agent_creation import agent_creation, agent_deprecated

logger = Logger(__file__, 'INFO')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Experiment Setup Module')
    parser.add_argument('--experiment', type=str, help='Experiment name', default='sock-shop')
    parser.add_argument('--setup', action='store_true', help='Setup the experiment')

    args = parser.parse_args()

    print(args)
    if args.setup:
        agent_creation(args.experiment)
    else:
        agent_deprecated(args.experiment)
