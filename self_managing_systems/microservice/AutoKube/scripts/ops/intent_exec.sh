#!/bin/bash

# Define color codes
RED='\033[1;31m'    # Bold Red for errors or critical inputs
GREEN='\033[1;32m'  # Bold Green for prompts and success messages
YELLOW='\033[1;33m' # Bold Yellow for input and warnings
BLUE='\033[1;34m'   # Bold Blue for informational messages
NC='\033[0m'        # No color

# Prompt the user for a natural language sentence
echo -e "${GREEN}Please enter a natural language sentence to determine its intent:${NC}"
read -r USER_INPUT

# Validate the input
if [[ -z "$USER_INPUT" ]]; then
    echo -e "${RED}Error: No input provided. Please enter a valid sentence.${NC}"
    exit 1
fi

# Display the captured input
echo -e "${BLUE}Captured sentence:${NC} $USER_INPUT"

# Call the Python function with the intent as a parameter
echo -e "${YELLOW}Determining intent and executing the function...${NC}"
python -m src.intent_exec.main --intent "$USER_INPUT"

# Check if the Python function executed successfully
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}Function executed successfully.${NC}"
else
    echo -e "${RED}Error: Function execution failed. Please check your Python script.${NC}"
    exit 1
fi
