import argparse
from msal import PublicClientApplication
import json
import requests
import random
import string
from datetime import datetime, timezone, timedelta
from azure.identity import DeviceCodeCredential
import yaml  # Import the yaml module

class LLMClient:

    _ENDPOINT = 'https://fe-26.qas.bing.net/sdf/'
    _SCOPES = ['https://substrate.office.com/llmapi/LLMAPI.dev']
    _API = 'chat/completions'

    def __init__(self, endpoint):
        self._app = PublicClientApplication(
            '68df66a4-cad9-4bfd-872b-c6ddde00d6b2',
            authority='https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47',
            allow_broker=True
        )
        if endpoint is not None:
            LLMClient._ENDPOINT = endpoint
        LLMClient._ENDPOINT += self._API
        print(f"Using endpoint: {LLMClient._ENDPOINT}")
        self._credential = DeviceCodeCredential(
            tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",
            client_id="68df66a4-cad9-4bfd-872b-c6ddde00d6b2",
        )
        self._token = self._credential.get_token("https://substrate.office.com/llmapi/LLMAPI.dev")

    def send_request(self, model_name, request):
        self._ensure_token()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self._token.token,
            'X-ModelType': model_name
        }
        body = json.dumps(request).encode('utf-8')
        response = requests.post(LLMClient._ENDPOINT, data=body, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}. Response: {response.text}")
        return response.json()

    def _ensure_token(self):
        expires_on = self._token.expires_on
        expires_at = datetime.fromtimestamp(expires_on, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        if expires_at - now < timedelta(minutes=5):
            self._token = self._credential.get_token("https://substrate.office.com/llmapi/LLMAPI.dev")

def get_o1_chat_completion(llm_client, engine, messages):
    request_data = {
        "messages": messages
    }
    return llm_client.send_request(engine, request_data)

if __name__ == '__main__':
    llm_client = LLMClient(None)

    secret_data = {
        'backend': 'AzureOpenAI',
        'AzureOpenAI': {
            'model': 'dev-gpt-o1-preview',
            'api_type': 'azure',
            'api_key': llm_client._token.token,
            'base_url': 'https://fe-26.qas.bing.net/sdf/',
            'api_version': '2024-10-21',
        }
    }

    with open('conf/secret_o1.yaml', 'w') as yaml_file:
        yaml.dump(secret_data, yaml_file)

    for _ in range(1):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        messages = [{"role": "user", "content": random_string}]
        response = get_o1_chat_completion(llm_client, "dev-gpt-o1-preview", messages)
        print(f"Input: {random_string}")
        print(f"Response: {response}")
