#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear_port_9090() {
    echo -e "${YELLOW}Checking if port 9090 is in use...${NC}"
    PID=$(lsof -t -i:9090)
    if [ -n "$PID" ]; then
        echo -e "${RED}Port 9090 is in use by process ID: $PID. Terminating process...${NC}"
        kill -9 $PID
        echo -e "${GREEN}Port 9090 cleared.${NC}"
    else
        echo -e "${BLUE}Port 9090 is not in use.${NC}"
    fi
}

echo -e "${GREEN}Please enter an operation: ${BLUE}setup${GREEN}, ${YELLOW}forward${GREEN}, or ${RED}deprecate${NC}"
read operation

case $operation in
    setup)
        echo -e "${YELLOW}Setting up Prometheus configuration...${NC}"
        kubectl create namespace monitoring
        echo -e "${GREEN}Created 'monitoring' namespace.${NC}"
        kubectl apply -f experiment_environment/prometheus
        echo -e "${GREEN}Applied Prometheus configuration.${NC}"
        ;;
    forward)
        clear_port_9090
        echo -e "${YELLOW}Forwarding Prometheus port...${NC}"
        PROMETHEUS_POD=$(kubectl get pods -n monitoring -l app=prometheus --no-headers -o custom-columns=":metadata.name" | head -n 1)
        if [[ -z "$PROMETHEUS_POD" ]]; then
            echo -e "${RED}No Prometheus pod found in the 'monitoring' namespace.${NC}"
        else
            echo -e "${BLUE}Found Prometheus pod: ${GREEN}$PROMETHEUS_POD${NC}"
            kubectl port-forward pod/$PROMETHEUS_POD 9090:9090 -n monitoring &
            FORWARD_PID=$!
            echo -e "${GREEN}Port-forwarding Prometheus at port 9090 (PID: $FORWARD_PID)...${NC}"
            wait $FORWARD_PID
        fi
        ;;
    deprecate)
        echo -e "${RED}Deleting monitoring namespace...${NC}"
        kubectl delete namespace monitoring
        echo -e "${GREEN}Monitoring namespace deleted.${NC}"
        ;;
    *)
        echo -e "${RED}Invalid operation! Please enter 'setup', 'forward', or 'deprecate'.${NC}"
        ;;
esac