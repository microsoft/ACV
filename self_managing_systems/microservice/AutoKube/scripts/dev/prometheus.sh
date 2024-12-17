#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

clear_port_9090() {
    printf "${YELLOW}Checking if port 9090 is in use...${NC}\n"
    PID=$(lsof -t -i:9090)
    if [ -n "$PID" ]; then
        printf "${RED}Port 9090 is in use by process ID: %s. Terminating process...${NC}\n" "$PID"
        kill -9 $PID
        printf "${GREEN}Port 9090 cleared.${NC}\n"
    else
        printf "${BLUE}Port 9090 is not in use.${NC}\n"
    fi
}

printf "${GREEN}Please enter an operation: ${BLUE}setup${GREEN}, ${YELLOW}forward${GREEN}, or ${RED}deprecate${NC}\n"
read operation

case $operation in
    setup)
        printf "${YELLOW}Setting up Prometheus configuration...${NC}\n"
        kubectl create namespace monitoring
        printf "${GREEN}Created 'monitoring' namespace.${NC}\n"
        kubectl apply -f experiment_environment/prometheus
        printf "${GREEN}Applied Prometheus configuration.${NC}\n"
        ;;
    forward)
        clear_port_9090
        printf "${YELLOW}Forwarding Prometheus port...${NC}\n"
        PROMETHEUS_POD=$(kubectl get pods -n monitoring -l app=prometheus --no-headers -o custom-columns=":metadata.name" | head -n 1)
        if [[ -z "$PROMETHEUS_POD" ]]; then
            printf "${RED}No Prometheus pod found in the 'monitoring' namespace.${NC}\n"
        else
            printf "${BLUE}Found Prometheus pod: ${GREEN}%s${NC}\n" "$PROMETHEUS_POD"
            kubectl port-forward pod/$PROMETHEUS_POD 9090:9090 -n monitoring &
            FORWARD_PID=$!
            printf "${GREEN}Port-forwarding Prometheus at port 9090 (PID: %s)...${NC}\n" "$FORWARD_PID"
            wait $FORWARD_PID
        fi
        ;;
    deprecate)
        printf "${RED}Deleting monitoring namespace...${NC}\n"
        kubectl delete namespace monitoring
        printf "${GREEN}Monitoring namespace deleted.${NC}\n"
        ;;
    *)
        printf "${RED}Invalid operation! Please enter 'setup', 'forward', or 'deprecate'.${NC}\n"
        ;;
esac
