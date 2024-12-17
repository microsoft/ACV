#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

: ${MINKUBE_CPUS:=6}
: ${MINIKUBE_MEMORY:=16384}

check_minikube_status() {
    minikube status | grep -q "host: Running"
}

setup_minikube() {
    printf "${GREEN}Setting up Minikube and required tools...${NC}\n"
    printf "${YELLOW}Requesting root access...${NC}\n"
    sudo -v

    minikube version
    if [ $? -eq 0 ]; then
        printf "${BLUE}Minikube is already installed.${NC}\n"
    else
        printf "${YELLOW}Installing Minikube...${NC}\n"
        curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
    fi

    kubectl version --client
    if [ $? -eq 0 ]; then
        printf "${BLUE}Kubectl is already installed.${NC}\n"
    else
        printf "${YELLOW}Installing kubectl...${NC}\n"
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl
    fi

    helm version
    if [ $? -eq 0 ]; then
        printf "${BLUE}Helm is already installed.${NC}\n"
    else
        printf "${YELLOW}Installing Helm...${NC}\n"
        curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
        chmod 700 get_helm.sh && ./get_helm.sh && rm get_helm.sh
    fi

    if ! check_minikube_status; then
        printf "${YELLOW}Starting Minikube with %s CPUs and %s MB memory...${NC}\n" "$MINKUBE_CPUS" "$MINIKUBE_MEMORY"
        minikube start --cpus=$MINKUBE_CPUS --memory=$MINIKUBE_MEMORY
    else
        printf "${BLUE}Minikube is already running.${NC}\n"
    fi

    printf "${YELLOW}Enabling Minikube addons...${NC}\n"
    minikube addons enable metrics-server
    printf "${GREEN}Minikube setup completed.${NC}\n"
}

deprecate_minikube() {
    printf "${RED}Stopping and deleting Minikube...${NC}\n"
    minikube stop
    minikube delete
    printf "${GREEN}Minikube has been stopped and deleted.${NC}\n"
}

printf "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${RED}deprecate${NC}\n"
read operation

case $operation in
    setup)
        setup_minikube
        ;;
    deprecate)
        deprecate_minikube
        ;;
    *)
        printf "${RED}Invalid operation! Please choose 'setup' or 'deprecate'.${NC}\n"
        ;;
esac
