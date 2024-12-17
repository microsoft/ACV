import subprocess
import json

def checkSLO(namespace, label_key, label_value, promQL_name):
    """
    Check the Service Level Objectives (SLO) for a given namespace and component.

    Parameters:
    - namespace (str): The Kubernetes namespace.
    - label_key (str): The label key to filter pods.
    - label_value (str): The label value to filter pods.
    - promQL_name (str): The Prometheus query name for latency checks.

    Returns:
    - bool: True if all SLO checks pass, False otherwise.
    """
    running_state = checkRunningState(namespace, label_key, label_value)
    resource_usage = checkResourceUsage(namespace, label_key, label_value)
    latency = checkLatency(promQL_name)

    if running_state and resource_usage and latency:
        print("SLO check passed.")
        return True
    else:
        print("SLO check failed.")
        return False

def checkRunningState(namespace, label_key, label_value):
    """
    Check if all pods in the specified namespace and label are running.

    Parameters:
    - namespace (str): The Kubernetes namespace.
    - label_key (str): The label key to filter pods.
    - label_value (str): The label value to filter pods.

    Returns:
    - bool: True if all pods are running, False otherwise.
    """
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '-n', namespace, '-l', f'{label_key}={label_value}', '-o', 'wide'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            print(f"Error executing kubectl command: {result.stderr}")
            return False

        lines = result.stdout.strip().split("\n")[1:]
        for line in lines:
            if not line.strip():
                print("No pods found matching the given label.")
                return False
            columns = line.split()
            status = columns[2]  # The third column is STATUS
            if status != "Running":
                print(f"Pod is not running with status: {status}")
                return False

        print("All pods are running.")
        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def getContainerLimits(pod_name, namespace):
    """
    Retrieve the resource limits for containers within a specified pod.

    Parameters:
    - pod_name (str): The name of the pod.
    - namespace (str): The Kubernetes namespace.

    Returns:
    - dict: A dictionary containing CPU and memory limits for each container.
    """
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pod', pod_name, '-n', namespace, '-o', 'json'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            print(f"Error getting pod details: {result.stderr}")
            return None

        pod_info = json.loads(result.stdout)

        container_limits = {}
        for container in pod_info['spec']['containers']:
            container_name = container['name']
            limits = container.get('resources', {}).get('limits', {})
            cpu_limit = limits.get('cpu', '0')
            memory_limit = limits.get('memory', '0')
            container_limits[container_name] = {
                'cpu': cpu_limit,
                'memory': memory_limit
            }

        return container_limits

    except Exception as e:
        print(f"An error occurred while getting container limits: {e}")
        return None

def checkResourceUsage(namespace, label_key, label_value):
    """
    Check if the resource usage of containers is within acceptable limits.

    Parameters:
    - namespace (str): The Kubernetes namespace.
    - label_key (str): The label key to filter pods.
    - label_value (str): The label value to filter pods.

    Returns:
    - bool: True if all containers are within resource limits, False otherwise.
    """
    try:
        pod_name_result = subprocess.run(
            ['kubectl', 'get', 'pod', '-n', namespace, '-l', f'{label_key}={label_value}', '-o', 'jsonpath={.items[0].metadata.name}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if pod_name_result.returncode != 0:
            print(f"Error getting pod name: {pod_name_result.stderr}")
            return False

        pod_name = pod_name_result.stdout.strip()
        if not pod_name:
            print("No pod name found with the given label.")
            return False

        container_limits = getContainerLimits(pod_name, namespace)
        if not container_limits:
            print("Failed to retrieve container limits.")
            return False

        top_result = subprocess.run(
            ['kubectl', 'top', 'pod', '-n', namespace, '-l', f'{label_key}={label_value}', '--containers'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if top_result.returncode != 0:
            print(f"Error executing kubectl top command: {top_result.stderr}")
            return False

        lines = top_result.stdout.strip().split("\n")[1:]

        for line in lines:
            columns = line.split()
            if len(columns) < 4:
                continue
            container_name = columns[1]
            cpu_usage = columns[2]
            memory_usage = columns[3]

            cpu_value = int(cpu_usage.replace('m', ''))
            memory_value = int(memory_usage.replace('Mi', ''))

            limits = container_limits.get(container_name, {})
            cpu_limit = limits.get('cpu', '0').replace('m', '')
            memory_limit = limits.get('memory', '0').replace('Mi', '')

            cpu_limit_value = int(cpu_limit) if cpu_limit.isdigit() else float('inf')
            memory_limit_value = int(memory_limit) if memory_limit.isdigit() else float('inf')

            if cpu_value > cpu_limit_value * 0.5 or memory_value > memory_limit_value * 0.5:
                print(f"Container {container_name} exceeds half of the resource limits: CPU = {cpu_usage} (Limit: {cpu_limit_value}m), "
                      f"Memory = {memory_usage} (Limit: {memory_limit_value}Mi)")
                return False
            else:
                print(f"Container {container_name}: CPU = {cpu_usage}, Memory = {memory_usage} "
                      f"(Limit: {cpu_limit_value}m CPU, {memory_limit_value}Mi Memory)")

        print("All containers meet the resource usage limits.")
        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def checkLatency(promQL_name):
    """
    Check the latency of a service using Prometheus queries.

    Parameters:
    - promQL_name (str): The Prometheus query name for latency checks.

    Returns:
    - bool: True if latency is below the threshold, False otherwise.
    """
    from .prometheus.promQL import query_prometheus
    promQL = f'histogram_quantile(0.99, rate(request_duration_seconds_bucket{{name="{promQL_name}"}}[1m]))'
    duration = '2m'
    step = '1m'

    result = query_prometheus(promQL, duration=duration, step=step)
    if not result or len(result) == 0:
        print("No valid data returned from Prometheus query.")
        return False

    last_entry = result[-1]
    timestamp, latency = last_entry[0], float(last_entry[1])

    if latency < 0.2:
        print(f"Latency: {latency}ms < 200ms at {timestamp}")
        return True
    else:
        print(f"Latency: {latency}ms > 200ms at {timestamp}")
        return False

if __name__ == "__main__":
    # Example usage for home-timeline-service in the social-network namespace
    checkSLO("social-network", "app", "home-timeline-service", "home-timeline-service")