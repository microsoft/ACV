import agentscope
from agentscope.message import Msg
from agentscope.pipelines import sequentialpipeline, forlooppipeline, whilelooppipeline

from ..agent.low_level import ServiceMaintainer
from ..agent import load_service_maintainer_config
from ..module import load_config, Prompter
from ..global_utils import get_openai_token_provider

global_config = load_config()

model_config = {
   "config_name": "azure",
   "model_type": "litellm_chat",
   "model_name": "azure/gpt-4o-mini-20240718",
}

import os
os.environ["AZURE_API_KEY"] = get_openai_token_provider()()
os.environ["AZURE_API_BASE"] = "https://cloudgpt-openai.azure-api.net/"
os.environ["AZURE_API_VERSION"] = "2024-04-01-preview"

agentscope.init(model_configs=[model_config])

def test_ServiceMaintainer():
    prompter = Prompter()
    service_maintainer_config = load_service_maintainer_config(
        global_config['project']['name'], 'catalogue'
    )
    prompter.load_prompt_template(
        global_config['agent']['service_prompt_template_path']
    )
    prompter.fill_system_message(service_maintainer_config)
    service_maintainer = ServiceMaintainer(
        name="catalogue",
        model_config_name="azure",
        system_prompt=prompter.system_message,
    )
    msg = Msg(
        content='Restart all the pods of your microservice component immediately.',
        name='user', role='user',echo=True,
    )

    forlooppipeline(
        loop_body_operators=[service_maintainer], max_loop=1, x=msg
    )


if __name__ == "__main__":
    test_ServiceMaintainer()