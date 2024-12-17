#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

printf "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${RED}deprecate${NC}\n"
read operation

case $operation in
    setup)
        printf "${GREEN}Enter the experiment name:${NC}\n"
        printf " - ${BLUE}social-network${NC}\n"
        printf " - ${BLUE}sock-shop${NC}\n"
        printf "${NC}"
        read experiment
        experiment=$(echo "$experiment" | xargs)

        if [ "$experiment" = "social-network" ]; then
            printf "${YELLOW}Setting up for social-network...${NC}\n"
            git clone https://github.com/delimitrou/DeathStarBench.git
            minikube mount "$(pwd)/DeathStarBench:/DeathStarBench" &
            kubectl create namespace social-network
            helm install "$experiment" "./experiment_environment/$experiment" --namespace "$experiment"
            printf "${GREEN}Setup for social-network completed successfully!${NC}\n"
        elif [ "$experiment" = "sock-shop" ]; then
            printf "${YELLOW}Setting up for sock-shop...${NC}\n"
            kubectl apply -f experiment_environment/sock-shop-backup
            printf "${GREEN}Setup for sock-shop completed successfully!${NC}\n"
        else
            printf "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}\n"
            exit 1
        fi
        ;;

    deprecate)
        printf "${GREEN}Enter the experiment name to deprecate:${NC}\n"
        printf " - ${BLUE}social-network${NC}\n"
        printf " - ${BLUE}sock-shop${NC}\n"
        printf "${NC}"
        read experiment
        experiment=$(echo "$experiment" | xargs)

        if [ "$experiment" = "social-network" ]; then
            printf "${YELLOW}Deprecating social-network...${NC}\n"
            kubectl delete namespace social-network
            printf "${GREEN}Deprecation of social-network completed successfully!${NC}\n"
        elif [ "$experiment" = "sock-shop" ]; then
            printf "${YELLOW}Deprecating sock-shop...${NC}\n"
            kubectl delete namespace sock-shop
            printf "${GREEN}Deprecation of sock-shop completed successfully!${NC}\n"
        else
            printf "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}\n"
            exit 1
        fi
        ;;

    *)
        printf "${RED}Invalid operation. Please enter either 'setup' or 'deprecate'.${NC}\n"
        exit 1
        ;;
esac
