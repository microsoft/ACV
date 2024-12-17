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

        if [ "$experiment" = "social-network" ] || [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Setting up the experiment: ${BLUE}$experiment${YELLOW}...${NC}"
            python -m src.agent_creation.main --experiment "$experiment" --setup
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Setup for ${BLUE}$experiment${GREEN} completed successfully!${NC}"
            else
                echo -e "${RED}Failed to setup the experiment: ${BLUE}$experiment${NC}"
                exit 1
            fi
        else
            echo -e "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}"
            exit 1
        fi
        ;;

    deprecate)  
        echo -e "${GREEN}Enter the experiment name to deprecate (${BLUE}social-network${GREEN} or ${BLUE}sock-shop${GREEN}):${NC}"
        read experiment
        experiment=$(echo $experiment | xargs)

        if [ "$experiment" = "social-network" ] || [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Deprecating the experiment: ${BLUE}$experiment${YELLOW}...${NC}"
            python -m src.agent_creation.main --experiment "$experiment"
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Deprecation of ${BLUE}$experiment${GREEN} completed successfully!${NC}"
            else
                echo -e "${RED}Failed to deprecate the experiment: ${BLUE}$experiment${NC}"
                exit 1
            fi
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
