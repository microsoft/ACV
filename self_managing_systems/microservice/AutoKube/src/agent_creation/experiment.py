import os
import time

from .utils import check_pods_ready

def startExperiment(experiment, logger):
    logger.info(f'Start ACV {experiment}...')
    if experiment == 'sock-shop':
        os.system(f'kubectl apply -f experiment_environment/{experiment}-backup')
    else:
        # Create new namespace first
        os.system(f'kubectl create namespace {experiment}')
        os.system(f'helm install {experiment} /Data2/v-fenglinyu/AutoKube/experiment_environment/{experiment} --namespace {experiment}')
    time.sleep(10)

    check_pods_ready(experiment, logger)
    logger.info(f'Finished setting up {experiment}.')

def deprecatedExperiment(experiment, logger):
    logger.info(f'Deprecating {experiment}...')
    if experiment == 'sock-shop':
        os.system(f'kubectl delete -f experiment_environment/{experiment}-backup')
    else:
        os.system(f'helm uninstall {experiment} --namespace {experiment}')
        os.system(f'kubectl delete namespace {experiment}')
    logger.info(f'Finished deprecated {experiment}.')
