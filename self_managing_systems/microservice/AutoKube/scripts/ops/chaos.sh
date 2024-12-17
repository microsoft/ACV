#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

check_helm_repo() {
    local repo_name=$1
    helm repo list | grep -q "$repo_name"
}

setup_chaos_mesh() {
    printf "${GREEN}Starting the installation of Chaos Mesh...${NC}\n"
    REPO_NAME="chaos-mesh"
    REPO_URL="https://charts.chaos-mesh.org"

    if ! check_helm_repo "$REPO_NAME"; then
        printf "${YELLOW}Adding Helm repo: ${BLUE}%s${NC}\n" "$REPO_NAME"
        helm repo add "$REPO_NAME" "$REPO_URL"
        helm repo update
        printf "${GREEN}Helm repo added and updated successfully.${NC}\n"
    else
        printf "${BLUE}Helm repo ${REPO_NAME} already exists.${NC}\n"
    fi

    printf "${YELLOW}Checking for 'chaos-mesh' namespace...${NC}\n"
    if ! kubectl get ns chaos-mesh &>/dev/null; then
        printf "${YELLOW}Creating namespace 'chaos-mesh'...${NC}\n"
        kubectl create ns chaos-mesh
        printf "${GREEN}Namespace 'chaos-mesh' created.${NC}\n"
    else
        printf "${BLUE}Namespace 'chaos-mesh' already exists.${NC}\n"
    fi

    printf "${YELLOW}Installing or upgrading Chaos Mesh...${NC}\n"
    helm upgrade --install "$REPO_NAME" chaos-mesh/"$REPO_NAME" -n chaos-mesh --version 2.6.3
    if [ $? -eq 0 ]; then
        printf "${GREEN}Chaos Mesh installation/upgrade completed.${NC}\n"
    else
        printf "${RED}Chaos Mesh installation/upgrade failed.${NC}\n"
        exit 1
    fi
}

uninstall_chaos_mesh() {
    printf "${RED}Uninstalling Chaos Mesh...${NC}\n"
    helm uninstall chaos-mesh -n chaos-mesh
    if [ $? -eq 0 ]; then
        printf "${GREEN}Chaos Mesh uninstalled successfully.${NC}\n"
    else
        printf "${RED}Error during Chaos Mesh uninstallation.${NC}\n"
    fi

    printf "${YELLOW}Deleting namespace 'chaos-mesh'...${NC}\n"
    kubectl delete ns chaos-mesh &>/dev/null
    if [ $? -eq 0 ]; then
        printf "${GREEN}Namespace 'chaos-mesh' deleted successfully.${NC}\n"
    else
        printf "${BLUE}Namespace 'chaos-mesh' already deleted or does not exist.${NC}\n"
    fi
}

list_chaos_injection_types() {
    printf "${GREEN}Available types of chaos injection:${NC}\n"
    if [[ -d "src/chaos_inject/chaos_yaml" ]]; then
        local found_file=false
        for file in src/chaos_inject/chaos_yaml/*.yaml; do
            if [[ -e "$file" ]]; then
                found_file=true
                printf -- "- ${BLUE}%s${NC}\n" "$(basename "$file" .yaml)"
            fi
        done
        if [[ $found_file == false ]]; then
            printf "${RED}No chaos injection types found.${NC}\n"
            exit 1
        fi
    else
        printf "${RED}Directory src/chaos_inject/chaos_yaml does not exist.${NC}\n"
        exit 1
    fi
}

list_kubernetes_namespaces() {
    printf "${GREEN}Available Kubernetes namespaces:${NC}\n"
    namespaces=$(kubectl get namespaces --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$namespaces" ]]; then
        printf "${RED}No namespaces found.${NC}\n"
        exit 1
    fi
    echo "$namespaces" | while read -r ns; do
        printf -- "- ${BLUE}%s${NC}\n" "$ns"
    done
}

list_services_in_namespace() {
    local namespace=$1
    printf "${GREEN}Available services in namespace '${BLUE}%s${GREEN}':${NC}\n" "$namespace"
    services=$(kubectl get services -n "$namespace" --no-headers -o custom-columns=":metadata.name")
    if [[ -z "$services" ]]; then
        printf "${RED}No services found in namespace '$namespace'.${NC}\n"
        exit 1
    fi
    echo "$services" | while read -r svc; do
        printf -- "- ${BLUE}$svc${NC}\n"
    done
}

inject_chaos() {
    list_chaos_injection_types
    printf "${GREEN}Please specify the type of chaos injection: ${BLUE}"
    read CHAOS_TYPE
    printf "${NC}"

    list_kubernetes_namespaces
    printf "${GREEN}Please specify the Kubernetes namespace: ${BLUE}"
    read NAMESPACE
    printf "${NC}"

    list_services_in_namespace "$NAMESPACE"
    printf "${GREEN}Please specify the service name: ${BLUE}"
    read SERVICE
    printf "${NC}"

    printf "${GREEN}Injecting chaos with the following parameters:${NC}\n"
    printf "  ${BLUE}Type:${NC} %s\n" "$CHAOS_TYPE"
    printf "  ${BLUE}Namespace:${NC} %s\n" "$NAMESPACE"
    printf "  ${BLUE}Service:${NC} %s\n" "$SERVICE"

    python3 -m src.chaos_inject.main --operation "inject" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
    if [ $? -eq 0 ]; then
        printf "${GREEN}Chaos injection completed successfully.${NC}\n"
    else
        printf "${RED}Chaos injection failed.${NC}\n"
        exit 1
    fi
}

deprecate_chaos() {
    list_chaos_injection_types
    printf "${GREEN}Please specify the type of chaos injection to deprecate: ${BLUE}"
    read CHAOS_TYPE
    printf "${NC}"

    list_kubernetes_namespaces
    printf "${GREEN}Please specify the Kubernetes namespace: ${BLUE}"
    read NAMESPACE
    printf "${NC}"

    list_services_in_namespace "$NAMESPACE"
    printf "${GREEN}Please specify the service name to deprecate chaos: ${BLUE}"
    read SERVICE
    printf "${NC}"

    printf "${GREEN}Deprecating chaos injection with the following parameters:${NC}\n"
    printf "  ${BLUE}Type:${NC} %s\n" "$CHAOS_TYPE"
    printf "  ${BLUE}Namespace:${NC} %s\n" "$NAMESPACE"
    printf "  ${BLUE}Service:${NC} %s\n" "$SERVICE"

    python3 -m src.chaos_inject.main --operation "deprecate" --namespace "$NAMESPACE" --component "$SERVICE" --chaostype "$CHAOS_TYPE"
    if [ $? -eq 0 ]; then
        printf "${GREEN}Chaos deprecation completed successfully.${NC}\n"
    else
        printf "${RED}Chaos deprecation failed.${NC}\n"
        exit 1
    fi
}

printf "${GREEN}Please select an operation:${NC}\n"
printf "${YELLOW}setup-mesh${NC}     - Install or upgrade Chaos Mesh\n"
printf "${YELLOW}uninstall-mesh${NC} - Uninstall Chaos Mesh and delete namespace\n"
printf "${YELLOW}inject${NC}         - Inject chaos into a service\n"
printf "${YELLOW}deprecate${NC}      - Deprecate an existing chaos injection\n"
printf "${GREEN}Enter your choice: ${BLUE}"
read OPERATION
printf "${NC}"

case $OPERATION in
    setup-mesh)
        setup_chaos_mesh
        ;;
    uninstall-mesh)
        uninstall_chaos_mesh
        ;;
    inject)
        inject_chaos
        ;;
    deprecate)
        deprecate_chaos
        ;;
    *)
        printf "${RED}Invalid operation selected. Please choose from 'setup-mesh', 'uninstall-mesh', 'inject', or 'deprecate'.${NC}\n"
        exit 1
        ;;
esac
