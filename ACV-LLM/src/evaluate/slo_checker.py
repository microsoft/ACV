import subprocess
import json

def checkSLO():
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
    try:
        # 运行 kubectl 命令并获取输出
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '-n', 'sock-shop', '-o', 'wide'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        # 如果命令执行失败，返回错误信息
        if result.returncode != 0:
            print(f"Error executing kubectl command: {result.stderr}")
            return False
        
        # 解析输出行（跳过表头）
        lines = result.stdout.strip().split("\n")[1:]
        
        # 检查每个 pod 的 STATUS 是否为 Running
        for line in lines:
            columns = line.split()
            status = columns[2]  # 第三列是 STATUS
            if status != "Running":
                print(f"Pod is not running with status: {status}")
                return False
        
        # 如果所有 pod 都是 Running 状态
        print("All pods are running.")
        return True
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def getContainerLimits(pod_name, namespace):
    try:
        # Run the command to get pod details in JSON format
        result = subprocess.run(
            ['kubectl', 'get', 'pod', pod_name, '-n', namespace, '-o', 'json'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if result.returncode != 0:
            print(f"Error getting pod details: {result.stderr}")
            return None

        # Parse the JSON output
        pod_info = json.loads(result.stdout)

        # Extract resource limits for each container
        container_limits = {}
        for container in pod_info['spec']['containers']:
            container_name = container['name']
            limits = container.get('resources', {}).get('limits', {})
            cpu_limit = limits.get('cpu', '0')  # default to '0' if not specified
            memory_limit = limits.get('memory', '0')  # default to '0' if not specified
            container_limits[container_name] = {
                'cpu': cpu_limit,
                'memory': memory_limit
            }

        return container_limits

    except Exception as e:
        print(f"An error occurred while getting container limits: {e}")
        return None

def checkResourceUsage():
    try:
        # Get the pod name dynamically (assumes there is only one pod with the label 'catalogue')
        pod_name_result = subprocess.run(
            ['kubectl', 'get', 'pod', '-n', 'sock-shop', '-l', 'name=catalogue', '-o', 'jsonpath={.items[0].metadata.name}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if pod_name_result.returncode != 0:
            print(f"Error getting pod name: {pod_name_result.stderr}")
            return False

        pod_name = pod_name_result.stdout.strip()

        # Get the container limits for the 'catalogue' pod
        container_limits = getContainerLimits(pod_name, 'sock-shop')
        if not container_limits:
            print("Failed to retrieve container limits.")
            return False

        # Run 'kubectl top pod' command and get output
        result = subprocess.run(
            ['kubectl', 'top', 'pod', '-n', 'sock-shop', '-l', 'name=catalogue', '--containers'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            print(f"Error executing kubectl top command: {result.stderr}")
            return False

        # Parse the output lines (skip header)
        lines = result.stdout.strip().split("\n")[1:]

        # Process each line, comparing CPU and memory usage to limits
        for line in lines:
            columns = line.split()
            container_name = columns[1]  # Container name
            cpu_usage = columns[2]       # CPU usage
            memory_usage = columns[3]    # Memory usage

            # Strip units (assuming CPU is in 'm' and memory is in 'Mi')
            cpu_value = int(cpu_usage.replace('m', ''))
            memory_value = int(memory_usage.replace('Mi', ''))

            # Get the limits for the current container
            limits = container_limits.get(container_name, {})
            cpu_limit = limits.get('cpu', '0').replace('m', '')
            memory_limit = limits.get('memory', '0').replace('Mi', '')

            # Convert limits to integer (if specified, else default to a very high value)
            cpu_limit_value = int(cpu_limit) if cpu_limit.isdigit() else float('inf')
            memory_limit_value = int(memory_limit) if memory_limit.isdigit() else float('inf')

            # Check if the container exceeds the CPU or memory limits
            if cpu_value > cpu_limit_value * 0.5 or memory_value > memory_limit_value * 0.5:
                print(f"Container {container_name} exceeds half of the resource limits: CPU = {cpu_usage} (Limit: {cpu_limit_value}m), "
                      f"Memory = {memory_usage} (Limit: {memory_limit_value}Mi)")
                return False
            else:
                # Print each container's CPU and memory usage
                print(f"Container {container_name}: CPU = {cpu_usage}, Memory = {memory_usage} "
                      f"(Limit: {cpu_limit_value}m CPU, {memory_limit_value}Mi Memory)")

        # If all containers meet the resource usage criteria
        print("All containers meet the resource usage limits.")
        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    
def checkLatency():
    from src.agent.tool_functions_for_maintainer import query_prometheus
    promQL = 'histogram_quantile(0.99, sum(rate(request_duration_seconds_bucket{name="catalogue"}[1m])) by (name, le))'
    duration = '2m'  # 查询的时间范围
    step = '1m'      # 每个时间步长

    # 调用 query_prometheus 函数，执行 Prometheus 查询
    result = query_prometheus(promQL, duration=duration, step=step)
    if not result or len(result) == 0:
        print("No valid data returned from Prometheus query.")
        return False

    last_entry = result[-1]
    timestamp, latency = last_entry[0], float(last_entry[1])

    # 判断是否小于 200ms
    if latency < 0.2:
        print(f"Latency: {latency * 1000}ms < 200ms at {timestamp}")
        return True
    else:
        print(f"Latency: {latency * 1000}ms > 200ms at {timestamp}")
        return False

if __name__ == "__main__":
    checkSLO()