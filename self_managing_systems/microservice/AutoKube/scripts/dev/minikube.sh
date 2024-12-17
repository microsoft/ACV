#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

: ${MINKUBE_CPUS:=6}
: ${MINIKUBE_MEMORY:=16384}

check_minikube_status() {
    minikube status | grep -q "host: Running"
}

setup_minikube() {
    echo -e "${GREEN}Setting up Minikube and required tools...${NC}"
    echo -e "${YELLOW}Requesting root access...${NC}"
    sudo -v

    minikube version
    if [ $? -eq 0 ]; then
        echo -e "${BLUE}Minikube is already installed.${NC}"
    else
        echo -e "${YELLOW}Installing Minikube...${NC}"
        curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
    fi

    kubectl version
    if [ $? -eq 0 ]; then
        echo -e "${BLUE}Kubectl is already installed.${NC}"
    else
        echo -e "${YELLOW}Installing kubectl...${NC}"
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl
    fi

    helm version
    if [ $? -eq 0 ]; then
        echo -e "${BLUE}Helm is already installed.${NC}"
    else
        echo -e "${YELLOW}Installing Helm...${NC}"
        curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
        chmod 700 get_helm.sh && ./get_helm.sh && rm get_helm.sh
    fi

    if ! check_minikube_status; then
        echo -e "${YELLOW}Starting Minikube with $MINKUBE_CPUS CPUs and $MINIKUBE_MEMORY MB memory...${NC}"
        minikube start --cpus=$MINKUBE_CPUS --memory=$MINIKUBE_MEMORY
    else
        echo -e "${BLUE}Minikube is already running.${NC}"
    fi

    echo -e "${YELLOW}Enabling Minikube addons...${NC}"
    minikube addons enable ingress
    echo -e "${GREEN}Minikube setup completed.${NC}"
}

deprecate_minikube() {
    echo -e "${RED}Stopping and deleting Minikube...${NC}"
    minikube stop
    minikube delete
    echo -e "${GREEN}Minikube has been stopped and deleted.${NC}"
}

echo -e "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${RED}deprecate${NC}"
read operation

case $operation in
    setup)
        setup_minikube
        ;;
    deprecate)
        deprecate_minikube
        ;;
    *)
        echo -e "${RED}Invalid operation! Please choose 'setup' or 'deprecate'.${NC}"
        ;;
esac