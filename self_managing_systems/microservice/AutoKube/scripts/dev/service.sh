#!/bin/bash

# Color codes
RED='\033[1;31m'    # Bold Red for errors or critical actions
GREEN='\033[1;32m'  # Bold Green for success or prompts
YELLOW='\033[1;33m' # Bold Yellow for warnings or ongoing actions
BLUE='\033[1;34m'   # Bold Blue for informational messages
NC='\033[0m'        # No color

# Prompt for operation type (setup or deprecate)
echo -e "${GREEN}Please enter an operation: ${BLUE}setup${GREEN} or ${BLUE}deprecate${NC}"
read operation

# Perform actions based on the operation
case $operation in
    setup)  # If "setup" is chosen
        # Prompt for the experiment (either social-network or sock-shop)
        echo -e "${GREEN}Enter the experiment name (${BLUE}social-network${GREEN} or ${BLUE}sock-shop${GREEN}):${NC}"
        read experiment

        # Trim whitespace from the experiment input
        experiment=$(echo $experiment | xargs)

        # Execute commands based on the experiment choice
        if [ "$experiment" = "social-network" ]; then
            echo -e "${YELLOW}Setting up for social-network...${NC}"
            git clone https://github.com/delimitrou/DeathStarBench.git
            minikube mount /Data2/v-fenglinyu/AutoKube/DeathStarBench:/DeathStarBench &
            python -m src.exp_setup.main --experiment social-network --setup
            echo -e "${GREEN}Setup for social-network completed successfully!${NC}"
        elif [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Setting up for sock-shop...${NC}"
            python -m src.exp_setup.main --experiment sock-shop --setup
            echo -e "${GREEN}Setup for sock-shop completed successfully!${NC}"
        else
            echo -e "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}"
            exit 1
        fi
        ;;

    deprecate)  # If "deprecate" is chosen
        echo -e "${GREEN}Enter the experiment name to deprecate (${BLUE}social-network${GREEN} or ${BLUE}sock-shop${GREEN}):${NC}"
        read experiment

        # Trim whitespace from the experiment input
        experiment=$(echo $experiment | xargs)

        # Execute deprecation commands based on the experiment choice
        if [ "$experiment" = "social-network" ]; then
            echo -e "${YELLOW}Deprecating social-network...${NC}"
            python -m src.exp_setup.main --experiment social-network
            echo -e "${GREEN}Deprecation of social-network completed successfully!${NC}"
        elif [ "$experiment" = "sock-shop" ]; then
            echo -e "${YELLOW}Deprecating sock-shop...${NC}"
            python -m src.exp_setup.main --experiment sock-shop
            echo -e "${GREEN}Deprecation of sock-shop completed successfully!${NC}"
        else
            echo -e "${RED}Invalid experiment name. Please enter either 'social-network' or 'sock-shop'.${NC}"
            exit 1
        fi
        ;;

    *)  # If the operation is not recognized
        echo -e "${RED}Invalid operation. Please enter either 'setup' or 'deprecate'.${NC}"
        exit 1
        ;;
esac
