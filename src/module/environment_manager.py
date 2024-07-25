# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
import time
import shutil
import traceback
import subprocess

from jsonpath_ng import parse
from .utils import load_config, load_yaml, save_yaml
from .base import Base

global_config = load_config()

working_dir = global_config['project']['path']
global_config['project']['path'] = global_config['project']['path'][:-1] + '-backup'

class EnvironmentManager(Base):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.unhealthy_pods: int = 0

    def setup(self, test_case: str = None):
        '''
        Setup the environment for experiment with specified test case
        - param test_case: str, test case to be setup
        '''
        if test_case:
            self.info('Setup the environment with test case: {}'.format(test_case))
            dataset_path = global_config['dataset']['path']
            test_case_config = load_yaml(os.path.join(dataset_path, f'{test_case}.yaml'))
            environment_config = test_case_config['environment']
            self.unhealthy_pods = environment_config['unhealthy_pods']

            try:
                file_path = None
                for file in environment_config['delete']:
                    os.remove(os.path.join(working_dir, file))
                
                for file in environment_config['create']:
                    file_path = os.path.join(working_dir, file['filename'])
                    with open(file_path, 'w') as f:
                        f.write(file['content'])
                    
                for file in environment_config['modify']:
                    filename = file['filename']
                    file_path = os.path.join(working_dir, filename)
                    target_config = load_yaml(file_path)
                    for item in file['create']:
                        jsonpath = item['jsonpath']
                        value = item['value']
                        parser = parse(jsonpath)
                        parser.update_or_create(target_config, value)
                    for item in file['modify']:
                        jsonpath = item['jsonpath']
                        value = item['value']
                        parser = parse(jsonpath)
                        parser.update(target_config, value)
                    for item in file['delete']:
                        jsonpath = item['jsonpath']
                        parser = parse(jsonpath)
                        parser.filter(lambda x: True, target_config)
            except Exception as e:
                self.error('Error in setting up the environment: {}'.format(e))
                traceback.print_exc()
                raise e
            if file_path:
                save_yaml(file_path, target_config)
        else:
            self.info('Setup the environment with default evnironment settings.')

        subprocess.run(['kubectl', 'apply', '-f', working_dir])
        self.info('Call check_pods_ready() to check if the environment is stable.')

        # restore files in the working directory
        if os.path.exists(working_dir):
            shutil.rmtree(working_dir)
        shutil.copytree(global_config['project']['path'], working_dir, dirs_exist_ok=True)

    def teardown(self):
        '''
        Teardown the environment
        '''
        self.info('Teardown the environment')
        # subprocess.run(['kubectl', 'delete', '-f', working_dir])
        subprocess.run(['kubectl', 'delete', 'namespace', global_config['project']['namespace']])
        if os.path.exists(working_dir):
            shutil.rmtree(working_dir)
        
        project_path = global_config['project']['path']
        shutil.copytree(project_path, working_dir, dirs_exist_ok=True)

    def check_pods_ready(self, interval: int = 15):
        '''
        Check if all pods are ready in environment
        - param interval: int, interval of checking in seconds
        '''
        try:
            self.info('checking pods status for ready...')
            ready_cnt = 0
            total_cnt = 1e9
            while ready_cnt + self.unhealthy_pods < total_cnt:
                jsonpath = r'{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'
                result = subprocess.run(['kubectl', 'get', 'pods', '-n', global_config['project']['namespace'], f'-o=jsonpath={jsonpath}'], capture_output=True, text=True).stdout.strip()
                lines = result.split('\n')
                ready_cnt = sum(1 for line in lines if line.strip().lower() == 'true')
                total_cnt = len(lines)
                self.info('Pods Ready: {}/{}'.format(ready_cnt, total_cnt))
                time.sleep(interval)
        except KeyboardInterrupt:
            self.warning('User interrupted the checking process.')
            return
        self.info('All pods are ready.')