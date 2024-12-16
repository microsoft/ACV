# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import subprocess
import json

def checkSLO():
    """
    Perform an end-to-end Service Level Objective (SLO) check.
    
    This function validates the running state of the pods, checks resource usage,
    and ensures latency is within acceptable limits.

    Returns:
    - bool: True if all SLO checks pass, False otherwise.
    """
    running_state = checkRunningState()
    resource_usage = checkResourceUsage()
    latency = checkLatency()

    if running_state and resource_usage and latency:
        print("SLO check passed.")
        return True
    else:
        print("SLO check failed.")
        return False

def checkRunningState():
    """
    Check if all pods in the 'sock-shop' namespace are in the 'Running' state.

    Returns:
    - bool: True if all pods are running, False otherwise.
    """
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '-n', 'sock-shop', '-o', 'wide'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            print(f"Error executing kubectl command: {result.stderr}")
            return False

        lines = result.stdout.strip().split("\n")[1:]  # Skip the header

        for line in lines:
            columns = line.split()
            status = columns[2]  # Pod status is in the third column
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
    Retrieve resource limits for all containers in a specified pod.

    Parameters:
    - pod_name (str): The name of the pod.
    - namespace (str): The namespace where the pod is located.

    Returns:
    - dict: A dictionary mapping container names to their CPU and memory limits.
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

def checkResourceUsage():
    """
    Verify if resource usage for containers does not exceed 50% of their limits.

    Returns:
    - bool: True if all containers meet the resource usage requirements, False otherwise.
    """
    try:
        pod_name_result = subprocess.run(
            ['kubectl', 'get', 'pod', '-n', 'sock-shop', '-l', 'name=catalogue', '-o', 'jsonpath={.items[0].metadata.name}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if pod_name_result.returncode != 0:
            print(f"Error getting pod name: {pod_name_result.stderr}")
            return False

        pod_name = pod_name_result.stdout.strip()

        container_limits = getContainerLimits(pod_name, 'sock-shop')
        if not container_limits:
            print("Failed to retrieve container limits.")
            return False

        result = subprocess.run(
            ['kubectl', 'top', 'pod', '-n', 'sock-shop', '-l', 'name=catalogue', '--containers'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            print(f"Error executing kubectl top command: {result.stderr}")
            return False

        lines = result.stdout.strip().split("\n")[1:]  # Skip the header

        for line in lines:
            columns = line.split()
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
    
def checkLatency():
    """
    Check if the 99th percentile latency for the "catalogue" service is below 200ms.

    Returns:
    - bool: True if the latency is below 200ms, False otherwise.
    """
    from src.agent.tool_functions_for_maintainer import query_prometheus
    promQL = 'histogram_quantile(0.99, sum(rate(request_duration_seconds_bucket{name="catalogue"}[1m])) by (name, le))'
    duration = '2m'
    step = '1m'

    result = query_prometheus(promQL, duration=duration, step=step)
    if not result or len(result) == 0:
        print("No valid data returned from Prometheus query.")
        return False

    last_entry = result[-1]
    timestamp, latency = last_entry[0], float(last_entry[1])

    if latency < 0.2:
        print(f"Latency: {latency * 1000}ms < 200ms at {timestamp}")
        return True
    else:
        print(f"Latency: {latency * 1000}ms > 200ms at {timestamp}")
        return False

if __name__ == "__main__":
    checkSLO()
