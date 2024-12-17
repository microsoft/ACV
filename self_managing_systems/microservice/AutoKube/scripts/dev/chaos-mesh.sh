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
    echo -e "${GREEN}Starting the installation of Chaos Mesh...${NC}"
    REPO_NAME="chaos-mesh"
    REPO_URL="https://charts.chaos-mesh.org"

    if ! check_helm_repo "$REPO_NAME"; then
        echo -e "${YELLOW}Adding Helm repo: ${BLUE}$REPO_NAME${NC}"
        helm repo add "$REPO_NAME" "$REPO_URL"
        helm repo update
        echo -e "${GREEN}Helm repo added and updated successfully.${NC}"
    else
        echo -e "${BLUE}Helm repo ${REPO_NAME} already exists.${NC}"
    fi

    echo -e "${YELLOW}Checking for 'chaos-mesh' namespace...${NC}"
    if ! kubectl get ns chaos-mesh &>/dev/null; then
        echo -e "${YELLOW}Creating namespace 'chaos-mesh'...${NC}"
        kubectl create ns chaos-mesh
        echo -e "${GREEN}Namespace 'chaos-mesh' created.${NC}"
    else
        echo -e "${BLUE}Namespace 'chaos-mesh' already exists.${NC}"
    fi

    echo -e "${YELLOW}Installing or upgrading Chaos Mesh...${NC}"
    helm upgrade --install "$REPO_NAME" chaos-mesh/"$REPO_NAME" -n chaos-mesh --version 2.6.3
    echo -e "${GREEN}Chaos Mesh installation/upgrade completed.${NC}"
}

deprecate_chaos_mesh() {
    echo -e "${RED}Uninstalling Chaos Mesh...${NC}"
    helm uninstall chaos-mesh -n chaos-mesh
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Chaos Mesh uninstalled successfully.${NC}"
    else
        echo -e "${RED}Error during Chaos Mesh uninstallation.${NC}"
    fi

    echo -e "${YELLOW}Deleting namespace 'chaos-mesh'...${NC}"
    kubectl delete ns chaos-mesh &>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Namespace 'chaos-mesh' deleted successfully.${NC}"
    else
        echo -e "${BLUE}Namespace 'chaos-mesh' already deleted or does not exist.${NC}"
    fi
}

echo -e "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${BLUE}deprecate${NC}"
read operation

case $operation in
    setup)
        setup_chaos_mesh
        ;;
    deprecate)
        deprecate_chaos_mesh
        ;;
    *)
        echo -e "${RED}Invalid operation! Please choose either 'setup' or 'deprecate'.${NC}"
        ;;
esac