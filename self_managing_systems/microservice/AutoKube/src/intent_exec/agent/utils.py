# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from ..module import (
    load_config,
    load_llm_config,
    get_prometheus_url
)

def load_gpt_4_turbo_config(cache_seed: int | None = 42):
    secret = load_llm_config('gpt-4-turbo.yaml')

    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_o1_preview_config(cache_seed: int | None = 42):
    secret = load_llm_config('o1-preview.yaml')

    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_service_maintainer_config(service_name:str):
    filename = f'component_list.yaml'
    print(f"Loading service maintainer config from {filename}")
    config = load_config(filename)
    for experiment in config:
        if service_name in config[experiment]:
            maintainer_config: dict = config[experiment][service_name]
    
    print(service_name)
    maintainer_config.update(config['common'])
    maintainer_config['prometheus_url'] = get_prometheus_url()
    return maintainer_config  
    

AWAITING_FLAG = '<AWAITING FOR RESPONSE>'
TERMINATE_FLAG = 'TERMINATE'
TERMINATE = lambda x: x.get("content", "").find("TERMINATE") != -1