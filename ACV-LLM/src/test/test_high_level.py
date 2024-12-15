import agentscope
from agentscope.parsers import MarkdownCodeBlockParser
from agentscope.message import Msg
from agentscope.agents import UserAgent
from agentscope.pipelines import sequentialpipeline, forlooppipeline, whilelooppipeline

from ..agent.low_level import ServiceMaintainer
from ..agent.high_level import ClusterManager
from ..agent import load_service_maintainer_config
from ..module import load_config, Prompter
from ..global_utils import get_openai_token

global_config = load_config()

model_config = {
   "config_name": "azure",
   "model_type": "litellm_chat",
   "model_name": "azure/gpt-4o-mini-20240718",
}

import os
os.environ["AZURE_API_KEY"] = get_openai_token()
os.environ["AZURE_API_BASE"] = "https://cloudgpt-openai.azure-api.net/"
os.environ["AZURE_API_VERSION"] = "2024-04-01-preview"

agentscope.init(model_configs=[model_config])

def test_group():
    components = ["user-service", "social-graph-service"]
    prompter = Prompter()
    prompter.load_prompt_template(global_config['agent']['manager_prompt_template_path'])
    prompter.fill_system_message({
        "namespace": global_config['project']['namespace'],
        "service_maintainers": components
    })
    manager = ClusterManager(
        name="manager",
        model_config_name="azure",
        system_prompt=prompter.system_message,
    )
    
    prompter = Prompter()
    prompter.load_prompt_template(global_config['agent']['service_prompt_template_path'])
    low_level_agents = []
    # for component in components:
    #     service_maintainer_config = load_service_maintainer_config(global_config['project']['name'], component)
    #     prompter.fill_system_message(service_maintainer_config)
    #     low_level_agents.append(
    #         ServiceMaintainer(
    #             name=component,
    #             model_config_name="azure",
    #             system_prompt=prompter.system_message,
    #         ).to_dist()
    #     )
    
    msg = Msg(
        name='user',
        content='Restart all the pods of your microservice component immediately.',
        role='user',
        echo=True,
    )
    x = None
    x = manager(msg)
    parser = MarkdownCodeBlockParser(language_name="json")
    res = parser.parse(x)
    print(res)
    # pipeline = whilelooppipeline(
    #     loop_body_operators=sequentialpipeline([manager] + low_level_agents),
    #     condition=lambda: True,
    #     x=msg,
    # )

if __name__ == '__main__':
    test_group()