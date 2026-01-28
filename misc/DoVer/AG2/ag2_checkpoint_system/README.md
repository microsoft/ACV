# AG2 Checkpoint System Documentation

## Overview

The AG2 Checkpoint System is a comprehensive solution for saving and restoring conversation states in multi-agent conversations using the AutoGen (AG2) framework. It enables persistent conversations that can be interrupted, resumed, and continued from any saved checkpoint.

## Features

- **Complete State Preservation**: Captures all agent configurations, conversation histories, and chat manager state
- **Smart Termination Pattern Detection**: Automatically detects and preserves custom termination patterns (e.g., "SOLUTION_FOUND")
- **LLM Configuration Serialization**: Saves complete LLM configurations including model parameters and authentication
- **Conversation Continuation**: Resume conversations from any checkpoint with additional rounds
- **Directory Organization**: Separates original sessions from continuation runs with datetime-based naming
- **Code Execution Support**: Properly handles code execution configurations during restoration

## Architecture

### Core Components

```
checkpoint_system/
├── __init__.py           # Package initialization
├── core.py               # Core checkpoint management and serialization
├── wrappers.py           # CheckpointingGroupChatManager wrapper
├── restoration.py        # Checkpoint loading and conversation continuation
├── exceptions.py         # Custom exception classes
├── utils.py              # Utility functions
└── README.md            # This documentation
```

### Key Classes

- **`CheckpointManager`**: Manages checkpoint creation, saving, and metadata tracking
- **`CheckpointingGroupChatManager`**: Wrapper around AG2's GroupChatManager with automatic checkpointing
- **`CheckpointData`**: Data structure representing a complete conversation checkpoint
- **`CheckpointRestorer`**: Handles loading checkpoints and recreating agent/manager states

## Quick Start Guide

### 1. Basic Usage Example

The easiest way to get started is with the provided `mathchat_with_checkpoints.py` example:

```bash
# Generate checkpoints during a conversation
cd /path/to/AG2_DoVer
python mathchat_with_checkpoints.py
```

This will create a session directory with checkpoints:
```
logs/session_YYYYMMDD_HHMMSS/
├── checkpoints/
│   ├── checkpoint_0_conversation_start_*.json
│   ├── checkpoint_1_message_appended_*.json
│   ├── checkpoint_2_message_appended_*.json
│   └── ...
├── chat_history.json
├── problem_statement.txt
└── session_metadata.json
```

### 2. Continue from a Checkpoint

Resume a conversation from any checkpoint:

```bash
# Continue from a specific checkpoint with additional rounds
python test_checkpoint_continuation.py logs/session_YYYYMMDD_HHMMSS/checkpoints/checkpoint_3_message_appended_*.json --rounds 10
```

This will create a continuation directory:
```
logs/session_YYYYMMDD_HHMMSS/continuation_YYYYMMDD_HHMMSS/
├── checkpoints/          # New checkpoints from continuation
├── continuation_metadata.json
└── ...
```

### 3. Custom Implementation

```python
from checkpoint_system import CheckpointManager, CheckpointingGroupChatManager
from autogen.agentchat.groupchat import GroupChat
from autogen.agentchat.conversable_agent import ConversableAgent

# Create agents
agents = [
    ConversableAgent("agent1", llm_config=your_llm_config),
    ConversableAgent("agent2", llm_config=your_llm_config)
]

# Create GroupChat
groupchat = GroupChat(agents=agents, messages=[])

# Create checkpoint manager
checkpoint_manager = CheckpointManager("./session_directory")

# Create checkpointing chat manager
chat_manager = CheckpointingGroupChatManager(
    checkpoint_manager=checkpoint_manager,
    groupchat=groupchat,
    name="chat_manager",
    problem_context="Your problem description"
)

# Start conversation with automatic checkpointing
chat_manager.initiate_chat(
    recipient=agents[0],
    message="Your initial message",
    max_turns=10
)
```

## Detailed Features

### Checkpoint Content

Each checkpoint contains:

```json
{
  "checkpoint_id": "checkpoint_3_message_appended_20241116_130239",
  "timestamp": "2024-11-16T13:02:39.123456",
  "step_number": 3,
  "context": "message_appended",
  "messages": [...],  // Complete conversation history
  "agent_states": {
    "agent_name": {
      "name": "agent_name",
      "system_message": "...",
      "llm_config": {...},          // Complete LLM configuration
      "termination_pattern": "SOLUTION_FOUND",  // Custom termination detection
      "code_execution_config": {...},
      "_oai_messages": {...}        // Conversation histories
    }
  },
  "manager_state": {
    "name": "chat_manager",
    "llm_config": {...},
    "termination_pattern": "SOLUTION_FOUND",  // Manager termination pattern
    "step_counter": 6,
    "current_speaker": "agent_name"
  },
  "metadata": {
    "session_dir": "session_20241116_130229",
    "problem_context": "Math problem solving"
  }
}
```

### Termination Pattern Detection

The system automatically detects and preserves termination patterns:

- **SOLUTION_FOUND**: Custom pattern for math/problem-solving scenarios
- **TERMINATE**: Default AG2 termination pattern
- **Custom**: Other lambda-based termination functions (marked but not auto-restorable)
- **None**: Default AG2 behavior

### LLM Configuration Serialization

Complete LLM configurations are preserved including:
- Model parameters (model name, temperature, max_tokens, etc.)
- API configuration (base_url, api_type, api_version)
- Authentication settings (azure_ad_token_provider support)
- All serializable configuration fields

## Testing and Validation

### Running Tests

```bash
# Test checkpoint creation and basic functionality
python test_mathchat_checkpoints.py

# Test checkpoint restoration and continuation
python test_checkpoint_continuation.py [checkpoint_file] --rounds [num_rounds]

# Test specific restoration functionality
python test_checkpoint_restoration.py
```

### Validation Checklist

- ✅ Checkpoints are created at conversation milestones
- ✅ Complete agent states are preserved
- ✅ LLM configurations are fully serialized
- ✅ Termination patterns are detected and restored
- ✅ Conversation histories are maintained
- ✅ Code execution configurations work after restoration
- ✅ Continuation sessions are properly isolated

## API Reference

### CheckpointManager

```python
class CheckpointManager:
    def __init__(self, session_dir: Union[str, Path])
    def save_checkpoint(self, checkpoint_data: CheckpointData) -> bool
    def load_checkpoint(self, checkpoint_id: str) -> CheckpointData
    def create_conversation_checkpoint(self, agents, manager, messages, step_number, context) -> CheckpointData
    def save_checkpoints_metadata(self) -> Path
```

### CheckpointingGroupChatManager

```python
class CheckpointingGroupChatManager(GroupChatManager):
    def __init__(self, checkpoint_manager: CheckpointManager, problem_context: str = "", **kwargs)
    def save_checkpoint(self, context: str = "manual") -> Optional[str]
    def continue_from_loaded_state(self, max_additional_rounds: int = 10) -> Tuple[bool, str]
```

### CheckpointRestorer

```python
class CheckpointRestorer:
    def continue_conversation_from_checkpoint(
        self, checkpoint_file: Union[str, Path], max_rounds: int = 10
    ) -> bool
    def recreate_agents_from_checkpoint(self, agent_states: Dict) -> List[ConversableAgent]
    def restore_agent_message_histories(self, agents: List, chat_manager) -> None
```

## Configuration Options

### Environment Setup

```python
# Required imports
from checkpoint_system import CheckpointManager, CheckpointingGroupChatManager
from autogen import ConversableAgent, GroupChat, LLMConfig

# LLM Configuration example
llm_config = LLMConfig(
    model="gpt-4",
    base_url="https://your-api-endpoint.com/",
    api_type="azure",
    api_version="2024-02-15-preview",
    max_tokens=4096,
    azure_ad_token_provider=your_token_provider
)
```

### Custom Termination Patterns

```python
# Custom termination for math problems
chat_manager = CheckpointingGroupChatManager(
    checkpoint_manager=checkpoint_manager,
    groupchat=groupchat,
    is_termination_msg=lambda msg: "SOLUTION_FOUND" in (msg.get("content", "") or ""),
    # ... other parameters
)

# Custom agent termination
agent = ConversableAgent(
    name="solver",
    is_termination_msg=lambda msg: "COMPLETE" in (msg.get("content", "") or ""),
    # ... other parameters
)
```

## Troubleshooting

### Common Issues

1. **Missing LLM Configuration**
   - Ensure `llm_config` is properly set on all agents and managers
   - Check that authentication providers are correctly configured

2. **Code Execution Errors**
   - Verify `code_execution_config` is properly set during agent creation
   - Ensure code execution environment is available during restoration

3. **Termination Pattern Issues**
   - Check that custom termination patterns are properly detected in logs
   - Verify termination messages match expected patterns exactly

4. **Directory Permissions**
   - Ensure write permissions for checkpoint directories
   - Check disk space for checkpoint files

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('checkpoint_system').setLevel(logging.DEBUG)
```

## Best Practices

1. **Regular Checkpoints**: Use automatic checkpointing at conversation milestones
2. **Descriptive Contexts**: Provide meaningful context strings for checkpoints
3. **Session Organization**: Use datetime-based session directories
4. **Resource Management**: Clean up old checkpoint sessions periodically
5. **Testing**: Validate checkpoint restoration before deploying to production
6. **Documentation**: Document custom termination patterns and configurations

## Examples

### Example 1: Math Problem Solving with Checkpoints

```python
# See: mathchat_with_checkpoints.py
python mathchat_with_checkpoints.py
```

### Example 2: Continuing a Conversation

```bash
# List available checkpoints
ls logs/session_*/checkpoints/

# Continue from a specific checkpoint
python test_checkpoint_continuation.py \
    logs/session_20241116_130229/checkpoints/checkpoint_3_message_appended_20241116_130239.json \
    --rounds 5
```

### Example 3: Custom Agent Configuration

```python
from checkpoint_system import CheckpointManager, CheckpointingGroupChatManager

# Custom agent with specific termination
custom_agent = ConversableAgent(
    name="specialist",
    system_message="You are a specialist in problem solving.",
    llm_config=llm_config,
    is_termination_msg=lambda msg: "FINAL_ANSWER" in msg.get("content", ""),
    code_execution_config={"work_dir": "code_execution"}
)

# Manager with custom termination
chat_manager = CheckpointingGroupChatManager(
    checkpoint_manager=CheckpointManager("./custom_session"),
    groupchat=GroupChat(agents=[custom_agent], messages=[]),
    is_termination_msg=lambda msg: "PROBLEM_SOLVED" in msg.get("content", ""),
    problem_context="Custom problem solving scenario"
)
```

## Version History

- **v1.0**: Initial implementation with basic checkpointing
- **v1.1**: Added termination pattern detection and restoration
- **v1.2**: Enhanced LLM configuration serialization
- **v1.3**: Added code execution support and continuation directories
- **v1.4**: Cleaned up debugging code and improved production readiness

## License

This checkpoint system is part of the AG2 AutoGen framework integration and follows the same licensing terms.

## Contributing

When contributing to the checkpoint system:

1. Ensure all new features include comprehensive tests
2. Update this documentation for any API changes
3. Maintain backward compatibility for checkpoint file formats
4. Follow the existing code style and logging patterns

For questions or issues, please refer to the test files and examples provided in this repository.