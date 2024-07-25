# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import json
import openai
from time import sleep
from openai import AzureOpenAI

from ..module.utils import load_config

global_config = load_config()
secret = load_config('secret.yaml')['endpoint']

def get_openai_token(token_cache_file: str = 'cloudgpt-apim-token-cache.bin'):
    '''
    acquire token from Azure AD for CloudGPT OpenAI

    Parameters
    ----------
    token_cache : str, optional
        path to the token cache file, by default 'cloudgpt-apim-token-cache.bin' in the current directory
    '''
    import msal
    import os

    token_cache_file = os.path.join(global_config['base_path'], token_cache_file)
    cache = msal.SerializableTokenCache()

    def save_cache():
        if cache.has_state_changed:
            with open(token_cache_file, "w") as cache_file:
                cache_file.write(cache.serialize())
    if os.path.exists(token_cache_file):
        cache.deserialize(open(token_cache_file, "r").read())

    scopes = [secret['auth_scope']]
    app = msal.PublicClientApplication(
        secret['auth_client_id'],
        authority=secret['authority'],
        token_cache=cache
    )
    result = None
    try:
        account = app.get_accounts()[0]
        result = app.acquire_token_silent(scopes, account=account)
        if result is not None and "access_token" in result:
            save_cache()
            return result['access_token']
        result = None
    except Exception:
        pass

    try:
        account = cache.find(cache.CredentialType.ACCOUNT)[0]
        refresh_token = cache.find(
            cache.CredentialType.REFRESH_TOKEN,
            query={
                "home_account_id": account["home_account_id"]
            })[0]
        result = app.acquire_token_by_refresh_token(
            refresh_token["secret"], scopes=scopes)
        if result is not None and "access_token" in result:
            save_cache()
            return result['access_token']
        result = None
    except Exception:
        pass

    if result is None:
        print("no token available from cache, acquiring token from AAD")
        # The pattern to acquire a token looks like this.
        flow = app.initiate_device_flow(scopes=scopes)
        print(flow['message'])
        result = app.acquire_token_by_device_flow(flow=flow)
        if result is not None and "access_token" in result:
            save_cache()
            return result['access_token']
        else:
            print(result.get("error"))
            print(result.get("error_description"))
            raise Exception(
                "Authentication failed for acquiring AAD token for CloudGPT OpenAI")
 

def get_completion(system_prompt:str | list, user_content:str | list) -> str:
    """
    Get the completion from the OpenAI API.
    - param system_prompt: The system prompt.
    - param user_content: The user content.
    return: The completion from the OpenAI API.
    """
    client = AzureOpenAI(
        api_key=get_openai_token(),
        api_version=secret['api_version'],
        azure_endpoint=secret['api_base']
    )
    messages = prompt_construction(system_prompt, user_content)
    try:
        response = client.chat.completions.create(
            model=secret['api_model'],
            messages=messages,
            temperature=0
            )
        return response.choices[0].message.content
    except openai.BadRequestError as e:
        err = json.loads(e.response.text)
        if err["error"]["code"] == "content_filter":
            print("Content filter triggered!")
            return None
        print(f"The OpenAI API request was invalid: {e}")
        return None
    except openai.APIConnectionError as e:
        print(f"The OpenAI API connection failed: {e}")
        sleep(secret['INTERVAL'])
        response = client.chat.completions.create(
            model=secret['api_model'],
            messages=messages,
            temperature=0
            )
        return response.choices[0].message.content
    except openai.RateLimitError as e:
        print(f"Token rate limit exceeded. Retrying after {secret['INTERVAL']} second...")
        sleep(secret['INTERVAL'])
        response = client.chat.completions.create(
            model=secret['api_model'],
            messages=messages,
            temperature=0
            )
        return response.choices[0].message.content
    except openai.AuthenticationError as e:
        print(f"Invalid API token: {e}")
        client.api_key = get_openai_token()
        response = client.chat.completions.create(
            model=secret['api_model'],
            messages=messages,
            temperature=0
            )
        return response.choices[0].message.content
    except openai.APIError as e:
        sleep(secret['INTERVAL'])
        response = client.chat.completions.create(
            model=secret['api_model'],
            messages=messages,
            temperature=0
            )
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred: {e}")

def prompt_construction(system_prompt: str | list, user_content: str| list) -> list[dict]:
    """
    Construct the prompt for summarizing the experience into an example.
    - param user_content: The user content.
    return: The prompt for summarizing the experience into an example.
    """

    prompt_message = []
    if isinstance(system_prompt, list):
        prompt_message.extend([{"role": "system", "content": message} for message in system_prompt])
    elif isinstance(system_prompt, str):
        prompt_message.append({"role": "system", "content": system_prompt})
    else:
        raise ValueError(f"Invalid system message type: {type(system_prompt)}")

    if isinstance(user_content, list):
        prompt_message.extend([{"role": "user", "content": message} for message in user_content])
    elif isinstance(user_content, str):
        prompt_message.append({"role": "user", "content": user_content})
    else:
        raise ValueError(f"Invalid user message type: {type(user_content)}")

    return prompt_message

if __name__ == '__main__':
    print(get_openai_token())