import subprocess
import time

def check_pods_ready(experiment, logger):
    '''
    Check if all pods are ready in environment
    - param interval: int, interval of checking in seconds
    '''
    try:
        logger.info('checking pods status for ready...')
        ready_cnt = 0
        total_cnt = 1e9
        start_time = time.time()
        max_wait_time = 600  # Maximum wait time in seconds
        while ready_cnt < total_cnt:
            if time.time() - start_time > max_wait_time:
                logger.warning('Timeout reached. Not all pods are ready.')
                return
            jsonpath = r'{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'
            result = subprocess.run(
                ['kubectl', 'get', 'pods', '-n', experiment, f'-o=jsonpath={jsonpath}'], 
                capture_output=True, text=True
            ).stdout.strip()
            lines = result.split('\n')
            ready_cnt = sum(1 for line in lines if line.strip().lower() == 'true')
            total_cnt = len(lines)
            logger.info('Pods Ready: {}/{}'.format(ready_cnt, total_cnt))
            time.sleep(10)

    except KeyboardInterrupt:
        logger.warning('User interrupted the checking process.')
        return
    logger.info('All pods are ready.')