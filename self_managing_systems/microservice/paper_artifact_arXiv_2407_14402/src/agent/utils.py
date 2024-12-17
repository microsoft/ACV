# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from ..module import (
    load_config,
    get_prometheus_url
)

def load_llm_config(cache_seed: int | None = 42):
    """
    Load the configuration for the language model (LLM) backend.

    Parameters:
    - cache_seed (int | None): Seed for caching the LLM model. Default is 42.

    Returns:
    - dict: Configuration dictionary for the LLM.
    """
    secret = load_config('secret.yaml')
    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], "Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_llm_o1_config(cache_seed: int | None = 42):
    """
    Load the configuration for the OpenAI-based LLM backend.

    Parameters:
    - cache_seed (int | None): Seed for caching the LLM model. Default is 42.

    Returns:
    - dict: Configuration dictionary for the OpenAI LLM.
    """
    secret = load_config('secret_openai.yaml')
    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], "Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_service_maintainer_config(namespace: str, service_name: str, filename: str = 'service_maintainers.yaml'):
    """
    Load the configuration for a specific service maintainer.

    Parameters:
    - namespace (str): The namespace in which the service resides.
    - service_name (str): The name of the service to load configuration for.
    - filename (str): The configuration file to load. Default is 'service_maintainers.yaml'.

    Returns:
    - dict: Configuration dictionary for the service maintainer.

    Raises:
    - ValueError: If the namespace or service_name is not found in the configuration file.
    """
    global_config = load_config()
    config = load_config(filename)
    
    if namespace not in config:
        raise ValueError(f"Namespace {namespace} not found in {filename}")
    if service_name not in config[namespace]:
        raise ValueError(f"Service {service_name} not found in {namespace}")
    
    maintainer_config: dict = config[namespace][service_name]
    maintainer_config.update(config['common'])  # Merge with common settings

    # Resolve file paths and append global project path
    for k, v in maintainer_config.items():
        if 'fp' in k:
            maintainer_config[k] = os.path.join(global_config['project']['path'], v)
    
    # Add Prometheus URL to the configuration
    maintainer_config['prometheus_url'] = get_prometheus_url()
    return maintainer_config

def init_agentscope():
    """
    Initialize the AgentScope framework with model configurations based on the backend.

    The method supports OpenAI, AzureOpenAI, and other LLM backends. It sets environment
    variables required for Azure and creates model configurations for use with AgentScope.

    Returns:
    - None
    """
    import agentscope
    from ..global_utils import get_openai_token_provider

    # Load secret configuration
    secret = load_config('secret.yaml')
    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], "Invalid backend"

    model_configs = []

    if backend == 'OpenAI':
        # OpenAI configuration
        openai_config = {
            "config_name": "openai",
            "model_type": "openai_chat",
            "model_name": secret["OpenAI"]["model"],
            "api_key": secret["OpenAI"]["api_key"],  
            "client_args": {
                # Additional client arguments can be specified here (e.g., retries)
            },
            "generate_args": {
                # Additional generation arguments can be specified here (e.g., temperature)
            },
        }
        model_configs.append(openai_config)

    elif backend == 'AzureOpenAI':
        # AzureOpenAI configuration
        azure_config = {
            "config_name": "azure",
            "model_type": "litellm_chat",
            "model_name": f"azure/{secret['AzureOpenAI']['model']}",
        }
        # Set environment variables for Azure API
        os.environ["AZURE_API_KEY"] = get_openai_token_provider()()
        os.environ["AZURE_API_BASE"] = "" # Should be set to the base URL of the Azure API
        os.environ["AZURE_API_VERSION"] = "2024-04-01-preview"
        model_configs.append(azure_config)

    # Initialize AgentScope with the prepared model configurations
    agentscope.init(model_configs=model_configs)
    print(
        "Init agentscope with config names: ",
        [config["config_name"] for config in model_configs]
    )

# Constants for message handling
AWAITING_FLAG = '<AWAITING FOR RESPONSE>'
TERMINATE_FLAG = 'TERMINATE'
TERMINATE = lambda x: x.get("content", "").find("TERMINATE") != -1
