# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import argparse
import subprocess

# Define the base path for the script
base_path = os.path.dirname(os.path.abspath(__file__))

def inject_chaos(chaos_yaml_path: str):
    """
    Inject chaos into the system using the specified YAML configuration.

    Parameters:
    - chaos_yaml_path (str): The path to the chaos YAML file.
    """
    print(f"Injecting chaos using: {chaos_yaml_path}")
    try:
        subprocess.run(['kubectl', 'apply', '-f', chaos_yaml_path], check=True)
        print("Chaos injection successful.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to inject chaos: {e}")
        raise

def delete_chaos(chaos_yaml_path: str):
    """
    Delete chaos from the system using the specified YAML configuration.

    Parameters:
    - chaos_yaml_path (str): The path to the chaos YAML file.
    """
    print(f"Deleting chaos using: {chaos_yaml_path}")
    try:
        subprocess.run(['kubectl', 'delete', '-f', chaos_yaml_path], check=True)
        print("Chaos deletion successful.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to delete chaos: {e}")
        raise

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Inject or delete chaos in the system.')
    parser.add_argument(
        '--operation', type=str, choices=['inject', 'deprecate'], required=True,
        help='Specify the operation: inject or deprecate.'
    )
    parser.add_argument(
        '--namespace', type=str, default='sock-shop',
        help='The namespace for the chaos experiment (default: sock-shop).'
    )
    parser.add_argument(
        '--component', type=str, default='catalogue',
        help='The name of the component to target (default: catalogue).'
    )
    parser.add_argument(
        '--chaostype', type=str, required=True,
        help='The type of chaos to inject (e.g., pod_failure).'
    )

    args = parser.parse_args()

    # Construct the path to the chaos YAML file
    chaos_yaml_path = os.path.join(base_path, 'chaos_yaml', f'{args.chaostype}.yaml')

    # Check if the YAML file exists
    if not os.path.exists(chaos_yaml_path):
        print(f"Chaos YAML file not found: {chaos_yaml_path}")
        exit(1)

    # Perform the specified operation
    if args.operation == 'inject':
        inject_chaos(chaos_yaml_path)
    elif args.operation == 'deprecate':
        delete_chaos(chaos_yaml_path)
