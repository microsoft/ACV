#!/bin/bash

# Define color codes
RED='\033[1;31m'    # Bold Red for errors or critical inputs
GREEN='\033[1;32m'  # Bold Green for prompts and success messages
YELLOW='\033[1;33m' # Bold Yellow for input and warnings
BLUE='\033[1;34m'   # Bold Blue for informational messages
NC='\033[0m'        # No color

# Function to list Locust files in experiment_environment/locust
list_locust_files() {
    echo -e "${GREEN}Available Locust files:${NC}"
    if [[ -d "experiment_environment/locust" ]]; then
        locust_files=()
        for file in experiment_environment/locust/*.py; do
            [[ -e "$file" ]] || { echo -e "${RED}No Locust files found in experiment_environment/locust.${NC}"; exit 1; }
            filename=$(basename "$file" .py) # Remove .py suffix
            locust_files+=("$filename")
            echo -e "- ${BLUE}$filename${NC}"
        done
        echo -e "${GREEN}Please choose a Locust file by entering its name:${NC}"
        read LOCUST_FILE

        # Validate user input
        if [[ ! " ${locust_files[@]} " =~ " $LOCUST_FILE " ]]; then
            echo -e "${RED}Invalid Locust file selected. Please run the script again and choose a valid file.${NC}"
            exit 1
        fi

        echo -e "${GREEN}You selected Locust file:${BLUE} $LOCUST_FILE${NC}"
        LOCUST_FILE="experiment_environment/locust/$LOCUST_FILE.py"
    else
        echo -e "${RED}Directory experiment_environment/locust does not exist.${NC}"
        exit 1
    fi
}

# Prompt user for input
echo -e "${GREEN}Please enter an operation: ${YELLOW}setup${GREEN} or ${YELLOW}deprecate${NC}"
read operation

case $operation in
    setup)  # If "setup" is selected
        # Fetch the pod name dynamically using kubectl
        echo -e "${GREEN}Fetching the nginx-thrift pod name...${NC}"
        POD_NAME=$(kubectl get pods -n social-network -l app=nginx-thrift -o jsonpath='{.items[0].metadata.name}')
        
        if [ -z "$POD_NAME" ]; then
            echo -e "${RED}Error: nginx-thrift pod not found in the social-network namespace.${NC}"
            exit 1
        fi
        
        # Forward the port (this will run in the background)
        echo -e "${YELLOW}Forwarding nginx-thrift pod port to localhost...${NC}"
        kubectl port-forward -n social-network pod/$POD_NAME 8080:8080 > /dev/null 2>&1 &
        FORWARD_PID=$! # Save the process ID of port-forwarding to terminate later
        
        HOST="http://localhost:8080"
        echo -e "${GREEN}Forwarded nginx-thrift pod to ${BLUE}$HOST${NC}"

        # List and prompt the user to select a Locust file
        list_locust_files

        # Prompt the user for user_count and spawn_rate
        sleep 2  # Wait for the port-forwarding to start
        echo -e "${GREEN}Enter the number of users:${NC}"
        read USER_COUNT
        echo -e "${GREEN}Enter the spawn rate:${NC}"
        read SPAWN_RATE
        
        RUN_TIME=${RUN_TIME:-"1h"} # Default run duration is 1 hour

        # Print parameter information
        echo -e "${GREEN}Setting up Locust with:${NC}"
        echo -e "  ${BLUE}Users:${NC} $USER_COUNT"
        echo -e "  ${BLUE}Spawn Rate:${NC} $SPAWN_RATE"
        echo -e "  ${BLUE}Locust File:${NC} $LOCUST_FILE"
        echo -e "  ${BLUE}Host:${NC} $HOST"
        echo -e "  ${BLUE}Run Time:${NC} $RUN_TIME"

        # Run Locust without showing output
        locust --headless \
               --users $USER_COUNT \
               --spawn-rate $SPAWN_RATE \
               --host $HOST \
               --run-time $RUN_TIME \
               -f $LOCUST_FILE > /dev/null 2>&1

        # Clean up: terminate the port-forwarding process after Locust completes
        echo -e "${YELLOW}Cleaning up port-forwarding process...${NC}"
        kill $FORWARD_PID
        echo -e "${GREEN}Port-forwarding process terminated.${NC}"
        ;;

    deprecate)  # If "deprecate" is selected
        echo -e "${YELLOW}Deprecating the Locust environment...${NC}"
        
        # Stop Locust (if there are running instances)
        pkill -f locust
        echo -e "${GREEN}Locust environment has been deprecated.${NC}"
        ;;
    
    *)  # Invalid operation
        echo -e "${RED}Invalid operation. Please enter ${YELLOW}setup${RED} or ${YELLOW}deprecate${RED}.${NC}"
        exit 1
        ;;
esac
