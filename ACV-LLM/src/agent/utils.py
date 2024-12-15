# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from ..module import (
    load_config,
    get_prometheus_url
)

def load_llm_config(cache_seed: int | None = 42):
    secret = load_config('secret.yaml')
    # secret = load_config('secret_openai.yaml')

    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_llm_o1_config(cache_seed: int | None = 42):
    # secret = load_config('secret.yaml')
    secret = load_config('secret_openai.yaml')

    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
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
            maintainer_config[k] = os.path.join(global_config['project']['path'], v)
    maintainer_config['prometheus_url'] = get_prometheus_url()
    return maintainer_config

def init_agentscope():
    import agentscope
    from ..global_utils import get_openai_token_provider
    secret = load_config('secret.yaml')
    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    model_configs = []
    if backend == 'OpenAI':
        openai_config = {
            "config_name": "openai",
            "model_type": "openai_chat",
            "model_name": secret["OpenAI"]["model"],
            "api_key": secret["OpenAI"]["api_key"],  
            "client_args": {
                # e.g. "max_retries": 3,
            },
            "generate_args": {
                # e.g. "temperature": 0.0
            },
        }
        model_configs.append(openai_config)
    elif backend == 'AzureOpenAI':
        azure_config = {
            "config_name": "azure",
            "model_type": "litellm_chat",
            "model_name": f"azure/{secret['AzureOpenAI']['model']}",
        }
        os.environ["AZURE_API_KEY"] = get_openai_token_provider()()
        os.environ["AZURE_API_BASE"] = "https://cloudgpt-openai.azure-api.net/"
        os.environ["AZURE_API_VERSION"] = "2024-04-01-preview"
        model_configs.append(azure_config)
    agentscope.init(model_configs=model_configs)
    print(
        "Init agentscope with config names: ",
        [config["config_name"] for config in model_configs]
    )
    

AWAITING_FLAG = '<AWAITING FOR RESPONSE>'
TERMINATE_FLAG = 'TERMINATE'
TERMINATE = lambda x: x.get("content", "").find("TERMINATE") != -1