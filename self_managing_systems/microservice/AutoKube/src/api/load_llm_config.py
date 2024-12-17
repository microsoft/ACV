import os
import yaml

# Determine the base directory where this script is located
base_path = os.path.dirname(os.path.abspath(__file__))


def load_config(config_file: str):
    """
    Load a YAML configuration file.

    Parameters:
    - config_file (str): The name of the configuration file to load.

    Returns:
    - dict: Parsed content of the YAML configuration file.
    """
    # Construct the full path to the configuration file
    config_path = os.path.join(base_path, config_file)
    
    # Open and read the YAML file
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def load_llm_config(cache_seed: int | None = 42):
    """
    Load the Language Model (LLM) configuration from a YAML file.

    Parameters:
    - cache_seed (int | None): Seed value for caching mechanisms. Defaults to 42.

    Returns:
    - dict: LLM configuration settings with the added cache_seed.
    
    Raises:
    - AssertionError: If the backend specified in the configuration is invalid.
    """
    # Load the configuration from 'gpt-4-turbo.yaml'
    secret = load_config('gpt-4-turbo.yaml')

    # Retrieve the backend type from the configuration
    backend = secret['backend']
    
    # Ensure the backend is one of the allowed options
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend: {backend}"

    # Extract the specific backend configuration
    llm_config = secret[backend]
    
    # Add the cache_seed to the configuration
    llm_config['cache_seed'] = cache_seed
    
    return llm_config
