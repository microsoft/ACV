# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import re
import json
import yaml
import subprocess
from jinja2 import Template
from yaml.composer import ComposerError


def get_ancestor_path(depth: int) -> str:
    """
    Get the ancestor directory path at a given depth.

    Args:
    - depth (int): Depth of the ancestor directory.

    Returns:
    - str: Path to the ancestor directory.
    """
    target_path = os.path.dirname(__file__)
    for _ in range(depth):
        target_path = os.path.dirname(target_path)
    return target_path


def load_config(config_file: str = 'global_config.yaml') -> dict:
    """
    Load a configuration file in YAML format.

    Args:
    - config_file (str): Name of the configuration file.

    Returns:
    - dict: Configuration data.
    """
    base_path = get_ancestor_path(2)
    config_dir = os.path.join(base_path, 'conf')
    try:
        with open(os.path.join(config_dir, config_file), 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print('Config file not found, using default.')
        with open(os.path.join(config_dir, 'global_config.yaml'), 'r') as f:
            content = f.read()

    template = Template(content)
    config = yaml.safe_load(template.render({'base_path': base_path}))
    return config


def get_resource_limit_by_pod(namespace: str = 'default', pod: str = None, pod_name: str = None) -> dict:
    """
    Retrieve resource limits for a pod using `kubectl`.

    Args:
    - namespace (str): Namespace of the pod.
    - pod (str): Pod ID.
    - pod_name (str): Name of the pod.

    Returns:
    - dict: Resource limits of the pod.
    """
    commands = [
        'kubectl', 'get', 'pods', '-n', namespace, '-o',
        r'jsonpath={range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources.limits}{"\n"}'
    ]
    if pod_name:
        pod = get_pod_by_name(namespace=namespace, name=pod_name)
        commands.append(pod)
    elif pod:
        commands.append(pod)
    result = subprocess.run(commands, capture_output=True, text=True).stdout
    pod2limits = {}
    for line in result.split('\n'):
        splited = line.strip().split('\t')
        if len(splited) == 2:
            pod2limits[splited[0]] = json.loads(splited[1])
    return pod2limits


def get_resource_usage_by_pod(namespace: str = 'default', pod: str = '', pod_name: str = None) -> dict:
    """
    Retrieve resource usage for a pod using `kubectl`.

    Args:
    - namespace (str): Namespace of the pod.
    - pod (str): Pod ID.
    - pod_name (str): Name of the pod.

    Returns:
    - dict: Resource usage of the pod.
    """
    commands = ['kubectl', 'top', 'pods', '-n', namespace, '--no-headers']
    if pod_name:
        pod = get_pod_by_name(namespace=namespace, name=pod_name)
        commands.append(pod)
    elif pod:
        commands.append(pod)
    result = subprocess.run(commands, capture_output=True, text=True).stdout
    pod2usage = {}
    for line in result.split('\n'):
        splited = re.split(r'\s+', line.strip())
        if len(splited) == 3:
            pod2usage[splited[0]] = {'cpu': splited[1], 'memory': splited[2]}
    return pod2usage


def format_resource_data(data: dict) -> dict:
    """
    Format resource data into a standard structure.

    Args:
    - data (dict): Raw resource data.

    Returns:
    - dict: Formatted resource data.
    """
    for k, v in data.items():
        data[k] = {
            'cpu': float(v['cpu'].replace('m', '')) / 1000 if 'm' in v['cpu'] else float(v['cpu']),
            'memory': float(v['memory'].replace('Mi', '')) / 1024 if 'Mi' in v['memory'] else float(v['memory'])
        }
    return data


def get_pod_by_name(namespace: str = 'default', name: str = '') -> str:
    """
    Retrieve the pod ID by its name.

    Args:
    - namespace (str): Namespace of the pod.
    - name (str): Name of the pod.

    Returns:
    - str: Pod ID.
    """
    result = subprocess.run(
        ['kubectl', 'get', 'pods', '-n', namespace, '-l', f'name={name}', '--no-headers'],
        capture_output=True, text=True
    ).stdout
    result = re.split(r'\s+', result.strip())[0]
    return result


def fill_content_in_yaml(yaml_fpath: str, placeholders: dict) -> str:
    """
    Replace placeholders in a YAML file with provided values.

    Args:
    - yaml_fpath (str): Path to the YAML file.
    - placeholders (dict): Placeholder values.

    Returns:
    - str: Updated YAML content.
    """
    with open(yaml_fpath, 'r') as file:
        yaml_content = file.read()
    template = Template(yaml_content)
    replaced_content = template.render(**placeholders)
    return replaced_content


def load_yaml(yaml_fpath: str) -> dict:
    """
    Load a YAML file into a Python dictionary.

    Args:
    - yaml_fpath (str): Path to the YAML file.

    Returns:
    - dict: YAML content.
    """
    if not os.path.exists(yaml_fpath):
        raise FileNotFoundError(f'File {yaml_fpath} not found')

    try:
        with open(yaml_fpath, 'r') as file:
            yaml_content = yaml.safe_load(file)
    except ComposerError:
        with open(yaml_fpath, 'r') as file:
            yaml_content = yaml.safe_load_all(file)
    return yaml_content


def save_yaml(yaml_fpath: str, data: dict):
    """
    Save a Python dictionary into a YAML file.

    Args:
    - yaml_fpath (str): Path to the YAML file.
    - data (dict): Data to be saved.
    """
    with open(yaml_fpath, 'w') as file:
        yaml.safe_dump(data, file, indent=2)


def get_cluster_ip() -> str:
    """
    Retrieve the cluster IP from Minikube.

    Returns:
    - str: Cluster IP.
    """
    try:
        minikube_ip = subprocess.run(
            ["minikube", "ip"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        raise ValueError('Failed to retrieve Minikube IP. Ensure Kubernetes access is configured.')
    return minikube_ip


def get_prometheus_url() -> str:
    """
    Generate the Prometheus URL from the cluster IP.

    Returns:
    - str: Prometheus URL.
    """
    minikube_ip = get_cluster_ip()
    assert minikube_ip != "", 'Minikube IP not found.'
    prometheus_url = f"http://{minikube_ip}:31090"
    return prometheus_url


if __name__ == "__main__":
    print(get_prometheus_url())
