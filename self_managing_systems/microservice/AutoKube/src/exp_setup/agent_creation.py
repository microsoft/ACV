import subprocess
import yaml

from ..api.cloudgpt_aoai import get_chat_completion
from tqdm import tqdm

def agent_creation(namespace):
    try:
        command = f"kubectl get deployment -n {namespace} -o yaml"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        result.check_returncode()
        deployment_yaml = result.stdout
        if deployment_yaml:
            deployments = yaml.safe_load(deployment_yaml)
            services = {}
            for item in tqdm(deployments.get('items', []), desc="Processing agent deployments"):
                name = item['metadata']['name']
                chat_message = [
                    {"role": "system", "content": "Generate a brief description for the service according to the name of the service."},
                    {"role": "user", "content": f"The name of the service is {name}."}
                ]
                engine = "gpt-4o-20240513"
                response = get_chat_completion(engine=engine, messages=chat_message)
                response_content_description = response.choices[0].message.content.strip()
                description = item['metadata'].get('annotations', {}).get('description', response_content_description)

                chat_message = [
                    {"role": "system", "content": "Generate a brief function for the service according to the name of the service."},
                    {"role": "user", "content": f"The name of the service is {name}."}
                ]
                response = get_chat_completion(engine=engine, messages=chat_message)
                response_content_function = response.choices[0].message.content.strip()
                description = item['metadata'].get('annotations', {}).get('description', response_content_function)
                function = item['metadata'].get('annotations', {}).get('function', response_content_function)
                services[name] = {
                    'service_name': name,
                    'description': description,
                    'function': function
                }
            output = {namespace: services}
            with open("src/conf/component_list.yaml", "a") as file:  # Changed "w" to "a" to append instead of overwrite
                yaml.dump(output, file)
                file.write("\n")  # Add a new line after appending
        else:
            print("No deployment found.")
    except subprocess.CalledProcessError as e:
        if "not found" in e.stderr.lower():
            return None
        raise Exception(f"Error getting deployment: {e.stderr}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}")

def agent_deprecated(namespace):
    try:
        with open("src/conf/component_list.yaml", "r") as file:
            components = yaml.safe_load(file)
            if namespace in components:
                del components[namespace]
                with open("src/conf/component_list.yaml", "w") as file:
                    yaml.dump(components, file)
            else:
                print(f"Namespace {namespace} not found in component list.")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}")
