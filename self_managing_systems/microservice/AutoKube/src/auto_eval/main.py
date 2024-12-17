# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from .evaluator import Evaluator

def main(instance: str, namespace: str, component: str):
    """
    Main function to execute the evaluator with specified parameters.

    Parameters:
    - instance (str): Name of the experiment instance to evaluate.
    - namespace (str): Namespace where the experiment is conducted.
    - component (str): Name of the component to be evaluated.
    """
    evaluator = Evaluator(instance, namespace, component)
    result = evaluator.callEvaluator()
    print("Evaluation Result:", result)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the evaluator with specified parameters.')
    parser.add_argument(
        '--experiment', type=str, default='sock-shop',
        help='Namespace of the experiment (default: sock-shop).'
    )
    parser.add_argument(
        '--component', type=str, default='catalogue',
        help='Name of the component to evaluate (default: catalogue).'
    )
    parser.add_argument(
        '--instance', type=str, default='pod_failure',
        help='Instance name of the experiment (default: pod_failure).'
    )
    
    # Parse command-line arguments
    args = parser.parse_args()
    print("Parsed Arguments:", args)

    # Call the main function with parsed arguments
    main(args.instance, args.experiment, args.component)
