# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from autogen import UserProxyAgent
from ..module import (
    load_config,
    get_prometheus_url
)

def load_llm_config(cache_seed: int | None = 42):
    secret = load_config('secret.yaml')['endpoint']

    llm_config = {
        "cache_seed": cache_seed,
        "model": secret['api_model'],
        "api_type": secret['api_type'],
        "api_key": secret['api_key'],
        "base_url": secret['api_base'],
        "api_version": secret['api_version'],
    }
    return llm_config

def load_service_maintainer_config(namespace:str, service_name:str, filename: str = 'service_maintainers.yaml'):
    global_config = load_config()
    config = load_config(filename)
    if namespace not in config:
        raise ValueError(f"Namespace {namespace} not found in {filename}")
    if service_name not in config[namespace]:
        raise ValueError(f"Service {service_name} not found in {namespace}")
    maintainer_config: dict = config[namespace][service_name]
    maintainer_config.update(config['common'])
    for k, v in maintainer_config.items():
        if 'fp' in k:
            maintainer_config[k] = global_config['project']['path'] + v
    maintainer_config['prometheus_url'] = get_prometheus_url()
    return maintainer_config

AWAITING_FLAG = '<AWAITING FOR RESPONSE>'
TERMINATE_FLAG = 'TERMINATE'
TERMINATE = lambda x: x.get("content", "").find("TERMINATE") != -1