# Privacy in Action: Towards Realistic Privacy Mitigation and Evaluation for LLM-Powered Agents

This project implements PrivacyChecker, a system for privacy mitigation in MCP and A2A live benchmark for LLM-powered agents. This code accompanies the research paper "Privacy in Action: Towards Realistic Privacy Mitigation and Evaluation for LLM-Powered Agents".

## Project Structure

### Core Files
- `MCP_main.py` - Main entry point for data point specific MCP context setup 
- `MCP_flow.py` - Implementation of the agent flow logic for MCP
- `A2A_main.py` - Main entry point for data point specific A2A context setup 
- `A2A_flow.py` - Implementation of the agent flow logic for A2A
- `auth.py` - Authentication for Google Calendar API

### Data Simulation Files
- `add_fake_mail.py` - Utility for creating simulated email data for privacy testing
- `add_fake_notion.py` - Utility for generating simulated Notion integration data for privacy evaluation

### Directories
- `mcp_servers/` - Contains server implementations and configurations for the MCP calls

### Final Data
- `PrivacyLens-Live`

## Requirements

### External Python Packages
```
python-dotenv
openai-agents
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
requests
agents
```

### API Keys and Authentication Required
- **Azure OpenAI**: Requires `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_VERSION` environment variables
- **Google APIs**: Requires `credentials.json` file for Gmail API access
- **Notion API**: Requires Notion API key for workspace integration

### Environment Variables
Create a `.env` file with the following variables:
```
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_API_VERSION=2024-09-01-preview
NOTION_API_KEY=your_notion_api_key
```

### Setup Files Needed
- `credentials.json` - Google API credentials file
- `token.json` - Generated after running auth.py

## Getting Started
1. Install required Python packages
2. Set up environment variables in `.env` file
3. Place Google API credentials in `credentials.json`
4. Run `auth.py` to generate authentication tokens
5. Prepare data files and agent cards
6. Run `MCP_main.py` or `A2A_main.py` depending on your use case