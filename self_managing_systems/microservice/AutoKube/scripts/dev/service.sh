#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

echo -e "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${BLUE}deprecate${NC}"
read operation

case $operation in
    setup)
        echo -e "${GREEN}Enter the experiment name (${BLUE}social-network${GREEN} or ${BLUE}sock-shop${GREEN}):${NC}"
        read experiment
        experiment=$(echo $experiment | xargs)

        if [ "$experiment" = "social-network" ]; then
            echo -e "${YELLOW}Setting up for social-network...${NC}"
            git clone https://github.com/delimitrou/DeathStarBench.git
            minikube mount "$(pwd)/DeathStarBench:/DeathStarBench" &
            kubectl create namespace social-network
            helm install "$experiment" "./experiment_environment/$experiment" --namespace "$experiment"
            echo -e "${GREEN}Setup for social-network completed successfully!${NC}"
        elif [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Setting up for sock-shop...${NC}"
            kubectl apply -f experiment_environment/sock-shop-backup
            echo -e "${GREEN}Setup for sock-shop completed successfully!${NC}"
        else
            echo -e "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}"
            exit 1
        fi
        ;;

    deprecate)
        echo -e "${GREEN}Enter the experiment name to deprecate (${BLUE}social-network${GREEN} or ${BLUE}sock-shop${GREEN}):${NC}"
        read experiment
        experiment=$(echo $experiment | xargs)

        if [ "$experiment" = "social-network" ]; then
            echo -e "${YELLOW}Deprecating social-network...${NC}"
            kubectl delete namespace social-network
            echo -e "${GREEN}Deprecation of social-network completed successfully!${NC}"
        elif [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Deprecating sock-shop...${NC}"
            kubectl delete namespace sock-shop
            echo -e "${GREEN}Deprecation of sock-shop completed successfully!${NC}"
        else
            echo -e "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}"
            exit 1
        fi
        ;;

    *)
        echo -e "${RED}Invalid operation. Please enter either 'setup' or 'deprecate'.${NC}"
        exit 1
        ;;
esac
