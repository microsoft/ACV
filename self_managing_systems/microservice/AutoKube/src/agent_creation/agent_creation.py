# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import subprocess
import yaml
from typing import Optional, Dict, Any

from ..api.cloudgpt_aoai import get_chat_completion
from tqdm import tqdm
from ..utils.logger import Logger  # Assuming Logger is available in this path

# Initialize the logger for this module with INFO level
logger = Logger(__file__, 'INFO')


def agent_creation(namespace: str) -> Optional[Dict[str, Any]]:
    """
    Creates agents within the specified Kubernetes namespace by processing deployment information.

    This function retrieves deployment details from the given namespace using `kubectl`, processes each
    deployment to generate descriptions and functions via a chat completion API, and appends the
    service information to a YAML configuration file.

    Parameters:
    - namespace (str): The Kubernetes namespace in which to create agents.

    Returns:
    - Optional[Dict[str, Any]]: A dictionary containing the namespace and its services if deployments are found;
      otherwise, None.

    Raises:
    - Exception: If there is an error executing the kubectl command or processing deployments.
    """
    try:
        # Command to get deployments in the specified namespace in YAML format
        command = f"kubectl get deployment -n {namespace} -o yaml"
        logger.info(f"Executing command: {command}")
        
        # Execute the command and capture the output
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        result.check_returncode()  # Raises CalledProcessError if the command failed
        
        deployment_yaml = result.stdout
        logger.debug(f"Retrieved deployment YAML: {deployment_yaml}")
        
        if deployment_yaml:
            deployments = yaml.safe_load(deployment_yaml)
            services = {}
            
            # Process each deployment item with a progress bar
            for item in tqdm(deployments.get('items', []), desc="Processing agent deployments"):
                name = item['metadata']['name']
                logger.debug(f"Processing deployment: {name}")
                
                # Generate a description for the service using chat completion
                description = generate_service_description(name)
                
                # Generate a function for the service using chat completion
                function = generate_service_function(name)
                
                # Retrieve existing annotations or use generated descriptions/functions
                annotations = item['metadata'].get('annotations', {})
                service_description = annotations.get('description', description)
                service_function = annotations.get('function', function)
                
                # Populate the services dictionary
                services[name] = {
                    'service_name': name,
                    'description': service_description,
                    'function': service_function
                }
                logger.info(f"Service '{name}' processed with description and function.")
            
            # Prepare the output dictionary
            output = {namespace: services}
            logger.debug(f"Output to be written to YAML: {output}")
            
            # Append the service information to the YAML configuration file
            append_to_yaml("src/conf/component_list.yaml", output)
            logger.info(f"Services successfully appended to 'component_list.yaml'.")
            
            return output
        else:
            logger.warning("No deployment found in the specified namespace.")
            return None

    except subprocess.CalledProcessError as e:
        error_message = e.stderr.lower()
        if "not found" in error_message:
            logger.error(f"Namespace '{namespace}' not found: {e.stderr}")
            return None
        else:
            logger.exception(f"Error getting deployment: {e.stderr}")
            raise Exception(f"Error getting deployment: {e.stderr}") from e
    except Exception as e:
        logger.exception("An unexpected error occurred during agent creation.")
        raise Exception(f"An unexpected error occurred: {str(e)}") from e


def agent_deprecated(namespace: str) -> None:
    """
    Deprecates agents within the specified Kubernetes namespace by removing their entries from the configuration file.

    This function reads the existing YAML configuration, removes the services associated with the given namespace,
    and writes the updated configuration back to the file.

    Parameters:
    - namespace (str): The Kubernetes namespace whose agents are to be deprecated.

    Returns:
    - None

    Raises:
    - Exception: If there is an error reading or writing the configuration file.
    """
    try:
        config_path = "src/conf/component_list.yaml"
        logger.info(f"Deprecating agents in namespace '{namespace}' by updating '{config_path}'.")
        
        # Load existing components from the YAML file
        with open(config_path, "r") as file:
            components = yaml.safe_load(file) or {}
            logger.debug(f"Current components loaded: {components}")
        
        # Check if the namespace exists in the components
        if namespace in components:
            del components[namespace]
            logger.info(f"Namespace '{namespace}' found and removed from component list.")
            
            # Write the updated components back to the YAML file
            with open(config_path, "w") as file:
                yaml.dump(components, file)
                logger.info(f"Updated component list written to '{config_path}'.")
        else:
            logger.warning(f"Namespace '{namespace}' not found in component list.")

    except FileNotFoundError:
        logger.error(f"Configuration file '{config_path}' does not exist.")
        raise Exception(f"Configuration file '{config_path}' does not exist.")
    except yaml.YAMLError as e:
        logger.exception(f"Error parsing YAML file: {e}")
        raise Exception(f"Error parsing YAML file: {e}") from e
    except Exception as e:
        logger.exception("An unexpected error occurred during agent deprecation.")
        raise Exception(f"An unexpected error occurred: {str(e)}") from e


def generate_service_description(name: str) -> str:
    """
    Generates a brief description for a service based on its name using a chat completion API.

    Parameters:
    - name (str): The name of the service.

    Returns:
    - str: The generated description of the service.
    """
    chat_message = [
        {"role": "system", "content": "Generate a brief description for the service according to the name of the service."},
        {"role": "user", "content": f"The name of the service is {name}."}
    ]
    engine = "gpt-4o-20240513"
    logger.debug(f"Generating description for service '{name}' with engine '{engine}'.")
    
    response = get_chat_completion(engine=engine, messages=chat_message)
    description = response.choices[0].message.content.strip()
    logger.debug(f"Generated description for '{name}': {description}")
    
    return description


def generate_service_function(name: str) -> str:
    """
    Generates a brief function for a service based on its name using a chat completion API.

    Parameters:
    - name (str): The name of the service.

    Returns:
    - str: The generated function description of the service.
    """
    chat_message = [
        {"role": "system", "content": "Generate a brief function for the service according to the name of the service."},
        {"role": "user", "content": f"The name of the service is {name}."}
    ]
    engine = "gpt-4o-20240513"
    logger.debug(f"Generating function for service '{name}' with engine '{engine}'.")
    
    response = get_chat_completion(engine=engine, messages=chat_message)
    function = response.choices[0].message.content.strip()
    logger.debug(f"Generated function for '{name}': {function}")
    
    return function


def append_to_yaml(file_path: str, data: Dict[str, Any]) -> None:
    """
    Appends data to a YAML file. If the file does not exist, it creates a new one.

    Parameters:
    - file_path (str): The path to the YAML file.
    - data (Dict[str, Any]): The data to append to the YAML file.

    Returns:
    - None

    Raises:
    - Exception: If there is an error writing to the file.
    """
    try:
        with open(file_path, "a") as file:
            yaml.dump(data, file)
            file.write("\n")  # Add a new line after appending
            logger.debug(f"Data appended to '{file_path}': {data}")
    except Exception as e:
        logger.exception(f"Failed to append data to '{file_path}': {e}")
        raise Exception(f"Failed to append data to '{file_path}': {e}") from e
