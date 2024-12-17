#!/bin/bash

# Define color codes for output
RED='\033[1;31m'    # Bold Red for errors or critical inputs
GREEN='\033[1;32m'  # Bold Green for prompts and success messages
YELLOW='\033[1;33m' # Bold Yellow for input and warnings
BLUE='\033[1;34m'   # Bold Blue for parameter values
NC='\033[0m'        # No color

# Function to list chaos injection types
list_chaos_injection_types() {
    echo -e "${GREEN}Available types of chaos injection:${NC}"
    if [[ -d "src/chaos_inject/chaos_yaml" ]]; then
        for file in src/chaos_inject/chaos_yaml/*.yaml; do
            [[ -e "$file" ]] || { echo -e "${RED}No chaos injection types found.${NC}"; exit 1; }
            echo -e "- ${BLUE}$(basename "$file" .yaml)${NC}"
        done
    else
        echo -e "${RED}Directory src/chaos_inject/chaos_yaml does not exist.${NC}"
        exit 1
    fi
}

# Function to list Kubernetes namespaces
list_kubernetes_namespaces() {
    echo -e "${GREEN}Available Kubernetes namespaces:${NC}"
    namespaces=$(kubectl get namespaces --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$namespaces" ]]; then
        echo -e "${RED}No namespaces found.${NC}"
        exit 1
    fi
    echo "$namespaces" | while read -r ns; do
        echo -e "- ${BLUE}$ns${NC}"
    done
}

# Function to list services in a namespace
list_services_in_namespace() {
    local namespace=$1
    echo -e "${GREEN}Available services in namespace '${BLUE}$namespace${GREEN}':${NC}"
    services=$(kubectl get services -n "$namespace" --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$services" ]]; then
        echo -e "${RED}No services found in namespace '$namespace'.${NC}"
        exit 1
    fi
    echo "$services" | while read -r svc; do
        echo -e "- ${BLUE}$svc${NC}"
    done
}

# Prompt user to select an operation: inject or deprecate
echo -e "${GREEN}Please select an operation: ${YELLOW}inject${GREEN} or ${YELLOW}deprecate${NC}"
read OPERATION

# Perform different actions based on the user's selected operation
case $OPERATION in
    inject)  # If the user selects "inject"
        # List and prompt for chaos injection type
        list_chaos_injection_types
        echo -e "${GREEN}Please specify the type of chaos injection:${NC}"
        read CHAOS_TYPE

        # List and prompt for Kubernetes namespace
        list_kubernetes_namespaces
        echo -e "${GREEN}Please specify the Kubernetes namespace:${NC}"
        read NAMESPACE

        # List and prompt for service name
        list_services_in_namespace "$NAMESPACE"
        echo -e "${GREEN}Please specify the service name:${NC}"
        read SERVICE

        # Display the entered parameters
        echo -e "${GREEN}Injecting chaos with the following parameters:${NC}"
        echo -e "  ${BLUE}Type:${NC} $CHAOS_TYPE"
        echo -e "  ${BLUE}Namespace:${NC} $NAMESPACE"
        echo -e "  ${BLUE}Service:${NC} $SERVICE"

        # Call the Python script with the provided parameters
        python3 -m src.chaos_inject.main --operation "$OPERATION" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
        ;;

    deprecate)  # If the user selects "deprecate"
        # List and prompt for chaos injection type
        list_chaos_injection_types
        echo -e "${GREEN}Please specify the type of chaos injection to deprecate:${NC}"
        read CHAOS_TYPE

        # List and prompt for Kubernetes namespace
        list_kubernetes_namespaces
        echo -e "${GREEN}Please specify the Kubernetes namespace:${NC}"
        read NAMESPACE

        # List and prompt for service name
        list_services_in_namespace "$NAMESPACE"
        echo -e "${GREEN}Please specify the service name to deprecate chaos:${NC}"
        read SERVICE

        # Display the entered parameters
        echo -e "${GREEN}Deprecating chaos injection with the following parameters:${NC}"
        echo -e "  ${BLUE}Type:${NC} $CHAOS_TYPE"
        echo -e "  ${BLUE}Namespace:${NC} $NAMESPACE"
        echo -e "  ${BLUE}Service:${NC} $SERVICE"

        # Call the Python script with the provided parameters
        python3 -m src.chaos_inject.main --operation "$OPERATION" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
        ;;

    *)  # For invalid operations
        echo -e "${RED}Invalid operation selected. Please choose either 'inject' or 'deprecate'.${NC}"
        exit 1
        ;;
esac
