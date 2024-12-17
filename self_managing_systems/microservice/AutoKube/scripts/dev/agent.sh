#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

printf "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${RED}deprecate${NC}\n"
read operation

namespaces=$(kubectl get ns -o jsonpath='{.items[*].metadata.name}')

printf "${GREEN}Available namespaces:${NC}\n"
for ns in $namespaces; do
    printf " - ${BLUE}%s${NC}\n" "$ns"
done

case $operation in
    setup)
        printf "${GREEN}Enter the namespace from the above list:${NC}\n"
        read namespace
        namespace=$(echo "$namespace" | xargs)

        printf "${YELLOW}Setting up the agents in namespace: ${BLUE}%s${YELLOW}...${NC}\n" "$namespace"
        python -m src.agent_creation.main --namespace "$namespace" --setup
        if [ $? -eq 0 ]; then
            printf "${GREEN}Setup of agents in ${BLUE}%s${GREEN} completed successfully!${NC}\n" "$namespace"
        else
            printf "${RED}Failed to set up the agents in namespace: ${BLUE}%s${NC}\n" "$namespace"
            exit 1
        fi
        ;;

    deprecate)
        printf "${GREEN}Enter the namespace from the above list to deprecate:${NC}\n"
        read namespace
        namespace=$(echo "$namespace" | xargs)

        printf "${YELLOW}Deprecating the namespace: ${BLUE}%s${YELLOW}...${NC}\n" "$namespace"
        python -m src.agent_creation.main --namespace "$namespace"
        if [ $? -eq 0 ]; then
            printf "${GREEN}Deprecation of namespace ${BLUE}%s${GREEN} completed successfully!${NC}\n" "$namespace"
        else
            printf "${RED}Failed to deprecate the namespace: ${BLUE}%s${NC}\n" "$namespace"
            exit 1
        fi
        ;;

    *)
        printf "${RED}Invalid operation. Please enter either 'setup' or 'deprecate'.${NC}\n"
        exit 1
        ;;
esac
