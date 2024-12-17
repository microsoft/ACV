import os
import yaml

base_path = os.path.dirname(os.path.abspath(__file__))

def load_llm_config(cache_seed: int | None = 42):
    secret = load_config('gpt-4-turbo.yaml')
    # secret = load_config('secret_openai.yaml')

    backend = secret['backend']
    assert backend in ['OpenAI', 'AzureOpenAI', 'Other'], f"Invalid backend"

    llm_config = secret[backend]
    llm_config['cache_seed'] = cache_seed
    return llm_config

def load_config(config_file: str):
    with open(os.path.join(base_path, config_file)) as f:
        return yaml.safe_load(f)