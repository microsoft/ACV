from __future__ import annotations
from typing import Any, Callable, Literal, Optional, ParamSpec, TypeVar, cast
import sys, os
import functools
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

api_scope_base = os.environ.get("API_SCOPE_BASE", None)
tenant_id = os.environ.get("TENANT_ID", None)

assert api_scope_base is not None, "API_SCOPE_BASE is not set, please set it in the environment variables"
assert tenant_id is not None, "TENANT_ID is not set, please set it in the environment variables"

__all__ = [
    "get_openai_token_provider",
    "get_openai_token",
    "get_openai_client",
    "get_chat_completion",
    "encode_image",
    "cloudgpt_available_models",
]


def check_module():
    try:
        import openai, azure.identity.broker  # type: ignore

        # del openai, azure.identity.broker
    except ImportError:
        print("Please install the required packages by running the following command:")
        print("pip install openai azure-identity-broker --upgrade")
        exit(1)


check_module()

import openai
from openai import OpenAI

_depRt = TypeVar("_depRt")
_depParam = ParamSpec("_depParam")


def _deprecated(message: str):
    def deprecated_decorator(
        func: Callable[_depParam, _depRt]
    ) -> Callable[_depParam, _depRt]:
        def deprecated_func(
            *args: _depParam.args, **kwargs: _depParam.kwargs
        ) -> _depRt:
            import traceback

            print(
                "\n ⚠️  \x1b[31m{} is a deprecated function. {}".format(
                    func.__name__, message
                )
            )
            traceback.print_stack()
            print("\x1b[0m")
            return func(*args, **kwargs)

        return deprecated_func

    return deprecated_decorator


def _validate_token(token: str) -> bool:
    import requests

    url = "https://cloudgpt-openai.azure-api.net/openai/ping"

    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        response = requests.get(url, headers=headers)
        assert response.status_code == 200 and response.text == "OK", response.text
        return True
    except Exception as e:
        print("Failed to validate token", e)
        return False


@functools.lru_cache(maxsize=3)
def get_openai_token_provider(
    token_cache_file: str = "cloudgpt-apim-token-cache.bin",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_azure_cli: Optional[bool] = None,
    use_broker_login: Optional[bool] = None,
    use_managed_identity: Optional[bool] = None,
    use_device_code: Optional[bool] = None,
    skip_access_validation: Optional[bool] = False,
    **kwargs: Any,
) -> Callable[[], str]:
    """
    Get a token provider function that could return a valid access token for CloudGPT OpenAI.
    
    The return value is a function that should be used with AzureOpenAIClient constructor as azure_ad_token_provider parameter.
    The following code snippet shows how to use it with AzureOpenAIClient:
    
    ```python
    token_provider = get_openai_token_provider()
    client = openai.AzureOpenAI(
        api_version="2024-06-01",
        azure_endpoint="https://cloudgpt-openai.azure-api.net/",
        azure_ad_token_provider=token_provider,
    )
    ```

    Parameters
    ----------
    token_cache_file : str, optional
        path to the token cache file, by default 'cloudgpt-apim-token-cache.bin' in the current directory
    client_id : Optional[str], optional
        client id for AAD app, by default None
    client_secret : Optional[str], optional
        client secret for AAD app, by default None
    use_azure_cli : Optional[bool], optional
        use Azure CLI for authentication, by default None. If AzCli has been installed and logged in,
        it will be used for authentication. This is recommended for headless environments and AzCLI takes
        care of token cache and token refresh.
    use_broker_login : Optional[bool], optional
        use broker login for authentication, by default None.
        If not specified, it will be enabled for known supported environments (e.g. Windows, macOS, WSL, VSCode),
        but sometimes it may not always could cache the token for long-term usage.
        In such cases, you can disable it by setting it to False.
    use_managed_identity : Optional[bool], optional
        use managed identity for authentication, by default None.
        If not specified, it will use user assigned managed identity if client_id is specified,
        For use system assigned managed identity, client_id could be None but need to set use_managed_identity to True.
    use_device_code : Optional[bool], optional
        use device code for authentication, by default None. If not specified, it will use interactive login on supported platform.
    skip_access_validation : Optional[bool], optional
        skip access token validation, by default False.

    Returns
    -------
    Callable[[], str]
        the token provider function that could return a valid access token for CloudGPT OpenAI
    """
    import shutil
    from azure.identity.broker import InteractiveBrowserBrokerCredential
    from azure.identity import (
        ManagedIdentityCredential,
        ClientSecretCredential,
        DeviceCodeCredential,
        AuthenticationRecord,
        AzureCliCredential,
    )
    from azure.identity import TokenCachePersistenceOptions
    import msal  # type: ignore

    global api_scope_base, tenant_id
    scope = api_scope_base + "/.default"

    token_cache_option = TokenCachePersistenceOptions(
        name=token_cache_file,
        enable_persistence=True,
        allow_unencrypted_storage=True,
    )

    def save_auth_record(auth_record: AuthenticationRecord):
        try:
            with open(token_cache_file, "w") as cache_file:
                cache_file.write(auth_record.serialize())
        except Exception as e:
            print("failed to save auth record", e)

    def load_auth_record() -> Optional[AuthenticationRecord]:
        try:
            if not os.path.exists(token_cache_file):
                return None
            with open(token_cache_file, "r") as cache_file:
                return AuthenticationRecord.deserialize(cache_file.read())
        except Exception as e:
            print("failed to load auth record", e)
            return None

    auth_record: Optional[AuthenticationRecord] = load_auth_record()

    current_auth_mode: Literal[
        "client_secret",
        "managed_identity",
        "az_cli",
        "interactive",
        "device_code",
        "none",
    ] = "none"

    implicit_mode = not (
        use_managed_identity or use_azure_cli or use_broker_login or use_device_code
    )

    if use_managed_identity or (implicit_mode and client_id is not None):
        if not use_managed_identity and client_secret is not None:
            assert (
                client_id is not None
            ), "client_id must be specified with client_secret"
            current_auth_mode = "client_secret"
            identity = ClientSecretCredential(
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
                cache_persistence_options=token_cache_option,
                authentication_record=auth_record,
            )
        else:
            current_auth_mode = "managed_identity"
            if client_id is None:
                # using default managed identity
                identity = ManagedIdentityCredential(
                    cache_persistence_options=token_cache_option,
                )
            else:
                identity = ManagedIdentityCredential(
                    client_id=client_id,
                    cache_persistence_options=token_cache_option,
                )
    elif use_azure_cli or (implicit_mode and shutil.which("az") is not None):
        current_auth_mode = "az_cli"
        identity = AzureCliCredential(tenant_id=tenant_id)
    else:
        if implicit_mode:
            # enable broker login for known supported envs if not specified using use_device_code
            if sys.platform.startswith("darwin") or sys.platform.startswith("win32"):
                use_broker_login = True
            elif os.environ.get("WSL_DISTRO_NAME", "") != "":
                use_broker_login = True
            elif os.environ.get("TERM_PROGRAM", "") == "vscode":
                use_broker_login = True
            else:
                use_broker_login = False
        if use_broker_login:
            current_auth_mode = "interactive"
            identity = InteractiveBrowserBrokerCredential(
                tenant_id=tenant_id,
                cache_persistence_options=token_cache_option,
                use_default_broker_account=True,
                parent_window_handle=msal.PublicClientApplication.CONSOLE_WINDOW_HANDLE,
                authentication_record=auth_record,
            )
        else:
            current_auth_mode = "device_code"
            identity = DeviceCodeCredential(
                tenant_id=tenant_id,
                cache_persistence_options=token_cache_option,
                authentication_record=auth_record,
            )

        try:
            auth_record = identity.authenticate(scopes=[scope])
            if auth_record:
                save_auth_record(auth_record)

        except Exception as e:
            print(
                f"failed to acquire token from AAD for CloudGPT OpenAI using {current_auth_mode}",
                e,
            )
            raise e

    try:
        from azure.identity import get_bearer_token_provider

        token_provider = get_bearer_token_provider(identity, scope)
        token_verified_cache: str = ""

        def token_provider_wrapper():
            nonlocal token_verified_cache
            token = token_provider()
            if token != token_verified_cache:
                if not skip_access_validation:
                    assert _validate_token(token), "failed to validate token"
                token_verified_cache = token
            return token

        return token_provider_wrapper
    except Exception as e:
        print("failed to acquire token from AAD for CloudGPT OpenAI", e)
        raise e


@_deprecated(
    "use get_openai_token_provider instead whenever possible "
    "and use it as the azure_ad_token_provider parameter in AzureOpenAIClient constructor. "
    "Please do not acquire token directly or use it elsewhere."
)
def get_openai_token(
    token_cache_file: str = "cloudgpt-apim-token-cache.bin",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_azure_cli: Optional[bool] = None,
    use_broker_login: Optional[bool] = None,
    use_managed_identity: Optional[bool] = None,
    use_device_code: Optional[bool] = None,
    skip_access_validation: Optional[bool] = False,
    **kwargs: Any,
) -> str:
    """
    get access token for CloudGPT OpenAI
    """
    return get_openai_token_provider(
        token_cache_file=token_cache_file,
        client_id=client_id,
        client_secret=client_secret,
        use_azure_cli=use_azure_cli,
        use_broker_login=use_broker_login,
        use_managed_identity=use_managed_identity,
        use_device_code=use_device_code,
        skip_access_validation=skip_access_validation,
        **kwargs,
    )()


"""
Available models for CloudGPT OpenAI
"""
cloudgpt_available_models = Literal[
    "gpt-35-turbo-20220309",
    "gpt-35-turbo-16k-20230613",
    "gpt-35-turbo-20230613",
    "gpt-35-turbo-1106",
    "gpt-4-20230321",
    "gpt-4-20230613",
    "gpt-4-32k-20230321",
    "gpt-4-32k-20230613",
    "gpt-4-1106-preview",
    "gpt-4-0125-preview",
    "gpt-4-visual-preview",
    "gpt-4-turbo-20240409",
    "gpt-4o-20240513",
    "gpt-4o-mini-20240718",
]


def encode_image(image_path: str, mime_type: Optional[str] = None) -> str:
    """
    Utility function to encode image to base64 for using in OpenAI API

    Parameters
    ----------
    image_path : str
        path to the image file

    mime_type : Optional[str], optional
        mime type of the image, by default None and will infer from the file extension if possible

    Returns
    -------
    str
        base64 encoded image url
    """
    import base64
    import mimetypes

    file_name = os.path.basename(image_path)
    mime_type = cast(
        Optional[str],
        mime_type if mime_type is not None else mimetypes.guess_type(file_name)[0],  # type: ignore
    )
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("ascii")

    if mime_type is None or not mime_type.startswith("image/"):
        print(
            "Warning: mime_type is not specified or not an image mime type. Defaulting to png."
        )
        mime_type = "image/png"

    image_url = f"data:{mime_type};base64," + encoded_image
    return image_url


@functools.lru_cache(maxsize=3)
def get_openai_client(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_azure_cli: Optional[bool] = None,
    use_broker_login: Optional[bool] = None,
    use_managed_identity: Optional[bool] = None,
    use_device_code: Optional[bool] = None,
) -> OpenAI:
    """
    Initialize OpenAI client for CloudGPT OpenAI.

    All parameters are optional and will use the default authentication method if not specified.

    Parameters
    ----------
    client_id : Optional[str], optional
        client id for AAD app, by default None
    client_secret : Optional[str], optional
        client secret for AAD app, by default None
    use_azure_cli : Optional[bool], optional
        use Azure CLI for authentication, by default None. If AzCli has been installed and logged in,
        it will be used for authentication. This is recommended for headless environments and AzCLI takes
        care of token cache and token refresh.
    use_broker_login : Optional[bool], optional
        use broker login for authentication, by default None.
        If not specified, it will be enabled for known supported environments (e.g. Windows, macOS, WSL, VSCode),
        but sometimes it may not always could cache the token for long-term usage.
        In such cases, you can disable it by setting it to False.
    use_managed_identity : Optional[bool], optional
        use managed identity for authentication, by default None.
        If not specified, it will use user assigned managed identity if client_id is specified,
        For use system assigned managed identity, client_id could be None but need to set use_managed_identity to True.
    use_device_code : Optional[bool], optional
        use device code for authentication, by default None. If not specified, it will use interactive login on supported platform.

    Returns
    -------
    OpenAI
        OpenAI client for CloudGPT OpenAI. Check https://github.com/openai/openai-python for more details.
    """
    token_provider = get_openai_token_provider(
        client_id=client_id,
        client_secret=client_secret,
        use_azure_cli=use_azure_cli,
        use_broker_login=use_broker_login,
        use_managed_identity=use_managed_identity,
        use_device_code=use_device_code,
    )
    client = openai.AzureOpenAI(
        api_version="2024-06-01",
        azure_endpoint="https://cloudgpt-openai.azure-api.net/",
        azure_ad_token_provider=token_provider,
    )
    return client


def get_chat_completion(
    model: Optional[cloudgpt_available_models] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_azure_cli: Optional[bool] = None,
    use_broker_login: Optional[bool] = None,
    use_managed_identity: Optional[bool] = None,
    use_device_code: Optional[bool] = None,
    **kwargs: Any,
):
    """
    Helper function to get chat completion from OpenAI API
    """

    engine: Optional[str] = kwargs.get("engine")

    model_name: Any = model
    if model_name is None:
        if engine is None:
            raise ValueError("model name must be specified by 'model' parameter")
        model_name = engine

    if "engine" in kwargs:
        del kwargs["engine"]

    client = get_openai_client(
        client_id=client_id,
        client_secret=client_secret,
        use_azure_cli=use_azure_cli,
        use_broker_login=use_broker_login,
        use_managed_identity=use_managed_identity,
        use_device_code=use_device_code,
    )

    response: Any = client.chat.completions.create(model=model_name, **kwargs)

    return response


def _test_call(**kwargs: Any):
    test_message = "What is the content?"

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini-20240718",
        messages=[{"role": "user", "content": test_message}],
        temperature=0.7,
        max_tokens=100,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )

    print(response.choices[0].message)


if __name__ == "__main__":
    # _test_call(use_broker_login=True)
    print(get_openai_token_provider()())
