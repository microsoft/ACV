"""
Checkpoint Restoration and Continuation Module

Provides classes and functions for loading checkpoints and continuing conversations
from saved states. Supports validation, agent recreation, and conversation continuation.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from .exceptions import InvalidCheckpointError, CheckpointError, RestorationError
from .utils import get_ag2_version

# Set up logging
logger = logging.getLogger(__name__)

def _build_llm_config_from_checkpoint(checkpoint_llm_config: Dict[str, Any]):
    """Convert serialized LLM config into a runtime-ready OpenAI config."""
    from autogen import LLMConfig

    config_data = dict(checkpoint_llm_config)
    config_data.pop("azure_ad_token_provider", None)
    config_data.setdefault("api_type", "openai")
    config_data.setdefault("base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    api_key = config_data.get("api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RestorationError("OPENAI_API_KEY must be set to recreate agents from checkpoints.")
    config_data["api_key"] = api_key
    return LLMConfig(**config_data)

class CheckpointValidator:
    """Validates checkpoint files and data for restoration compatibility."""
    
    SUPPORTED_CHECKPOINT_TYPES = {'message_appended'}
    UNSUPPORTED_CHECKPOINT_TYPES = {
        'speaker_reply_generated': "Half-integer checkpoints are NOT supported",
        'conversation_start': "Conversation start checkpoints are not suitable for continuation",
        'conversation_end': "Conversation end checkpoints cannot be continued"
    }
    
    @classmethod
    def validate_checkpoint_file(cls, checkpoint_file: Path) -> None:
        """
        Validate checkpoint file before attempting to load.
        
        Args:
            checkpoint_file: Path to checkpoint file
            
        Raises:
            InvalidCheckpointError: If checkpoint file is not suitable for restoration
        """
        if not checkpoint_file.exists():
            raise InvalidCheckpointError(f"Checkpoint file not found: {checkpoint_file}")
        
        if checkpoint_file.suffix != '.json':
            raise InvalidCheckpointError(f"Checkpoint file must be a JSON file: {checkpoint_file}")
        
        filename = checkpoint_file.name
        
        # Check for explicitly unsupported types
        for unsupported_type, error_msg in cls.UNSUPPORTED_CHECKPOINT_TYPES.items():
            if unsupported_type in filename:
                raise InvalidCheckpointError(
                    f"{error_msg}.\n"
                    f"File: {filename}\n"
                    f"Please use a message_appended checkpoint (integer step) instead."
                )
    
    @classmethod
    def validate_checkpoint_data(cls, checkpoint_data: Dict[str, Any]) -> None:
        """
        Validate checkpoint data content with strict assertions.
        
        Args:
            checkpoint_data: Loaded checkpoint data
            
        Raises:
            InvalidCheckpointError: If checkpoint data is invalid or unsupported
        """
        # Check required top-level fields
        required_fields = ['checkpoint_id', 'current_round', 'groupchat_state', 'agent_states', 'manager_state']
        for field in required_fields:
            if field not in checkpoint_data:
                raise InvalidCheckpointError(f"Checkpoint must contain '{field}' field")
        
        # Validate groupchat_state structure
        groupchat_state = checkpoint_data['groupchat_state']
        required_groupchat_fields = ['messages', 'agents']
        for field in required_groupchat_fields:
            if field not in groupchat_state:
                raise InvalidCheckpointError(f"GroupChat state must contain '{field}' field")
        
        # Validate manager_state structure
        manager_state = checkpoint_data['manager_state']
        required_manager_fields = ['name', 'system_message', 'human_input_mode', '_max_consecutive_auto_reply', 'llm_config']
        for field in required_manager_fields:
            if field not in manager_state:
                raise InvalidCheckpointError(f"Manager state must contain '{field}' field")
        
        # Validate agent_states structure
        agent_states = checkpoint_data['agent_states']
        if not agent_states:
            raise InvalidCheckpointError("Agent states cannot be empty")
        
        # Validate each agent state
        for agent_name, agent_state in agent_states.items():
            if agent_name == 'chat_manager':  # Skip if chat_manager is wrongly in agent_states
                continue
                
            required_agent_fields = ['name', 'system_message', 'human_input_mode', '_max_consecutive_auto_reply', 'description', 'llm_config']
            for field in required_agent_fields:
                if field not in agent_state:
                    raise InvalidCheckpointError(f"Agent '{agent_name}' state must contain '{field}' field")
            
            # Validate LLM config structure if present
            llm_config = agent_state['llm_config']
            if llm_config is not None:
                    required_llm_fields = ['model']
                for field in required_llm_fields:
                    if field not in llm_config:
                        raise InvalidCheckpointError(f"LLM config for agent '{agent_name}' must contain '{field}' field")
            
            # Validate code execution configuration - ensure it exists if the agent had code execution enabled
            code_execution_config = agent_state.get('code_execution_config')
            if 'code_execution_config' not in agent_state:
                raise InvalidCheckpointError(f"Agent '{agent_name}' state must contain 'code_execution_config' field (can be null)")
            
            # If code execution config exists, validate its structure
            if code_execution_config is not None:
                if not isinstance(code_execution_config, dict):
                    raise InvalidCheckpointError(f"Agent '{agent_name}' code_execution_config must be a dictionary or null")
                
                # Two valid formats:
                # 1. {"enabled": false} - for agents without code execution
                # 2. {"work_dir": "...", "use_docker": ...} - for agents with code execution enabled
                if "enabled" in code_execution_config:
                    # Format 1: Simple enabled/disabled flag
                    if not isinstance(code_execution_config.get("enabled"), bool):
                        raise InvalidCheckpointError(f"Agent '{agent_name}' code_execution_config 'enabled' field must be boolean")
                elif "work_dir" in code_execution_config or "use_docker" in code_execution_config:
                    # Format 2: Full configuration - validate required fields
                    required_code_fields = ['work_dir', 'use_docker']
                    for field in required_code_fields:
                        if field not in code_execution_config:
                            raise InvalidCheckpointError(f"Agent '{agent_name}' code_execution_config must contain '{field}' field")
                else:
                    # Invalid format
                    raise InvalidCheckpointError(f"Agent '{agent_name}' code_execution_config must contain either 'enabled' or 'work_dir'/'use_docker' fields")
        
        # Validate manager LLM config structure
        manager_llm_config = manager_state['llm_config']
        if manager_llm_config is not None:
                    required_llm_fields = ['model']
            for field in required_llm_fields:
                if field not in manager_llm_config:
                    raise InvalidCheckpointError(f"LLM config for chat manager must contain '{field}' field")
        
        # Validate checkpoint type from checkpoint_id
        checkpoint_id = checkpoint_data.get('checkpoint_id', '')
        
        # Check for supported type
        if not any(supported_type in checkpoint_id for supported_type in cls.SUPPORTED_CHECKPOINT_TYPES):
            # Check if it's a known unsupported type
            for unsupported_type, error_msg in cls.UNSUPPORTED_CHECKPOINT_TYPES.items():
                if unsupported_type in checkpoint_id:
                    raise InvalidCheckpointError(
                        f"{error_msg}. "
                        f"Found checkpoint type: {checkpoint_id}. "
                        f"Please use a message_appended checkpoint (integer step) instead."
                    )
            
            # Unknown checkpoint type
            raise InvalidCheckpointError(
                f"Unsupported checkpoint type: {checkpoint_id}. "
                f"Only 'message_appended' checkpoints are supported."
            )


class CheckpointLoader:
    """Loads and validates checkpoint data from files."""
    
    def __init__(self, validator: Optional[CheckpointValidator] = None):
        self.validator = validator or CheckpointValidator()
    
    def load_checkpoint(self, checkpoint_file: Union[str, Path]) -> Dict[str, Any]:
        """
        Load and validate checkpoint data from JSON file.
        
        Args:
            checkpoint_file: Path to checkpoint file
            
        Returns:
            Loaded and validated checkpoint data
            
        Raises:
            InvalidCheckpointError: If checkpoint is invalid or unsupported
            CheckpointError: If loading fails
        """
        checkpoint_path = Path(checkpoint_file)
        
        logger.info(f"Loading checkpoint: {checkpoint_path.name}")
        
        try:
            # Pre-validate file
            self.validator.validate_checkpoint_file(checkpoint_path)
            
            # Load checkpoint data
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            # Validate checkpoint data
            self.validator.validate_checkpoint_data(checkpoint_data)
            
            logger.info("✅ Checkpoint loaded successfully")
            logger.info(f"📊 Checkpoint ID: {checkpoint_data['checkpoint_id']}")
            logger.info(f"📊 Round: {checkpoint_data['current_round']}")
            logger.info(f"📊 Messages: {len(checkpoint_data['groupchat_state']['messages'])}")
            
            return checkpoint_data
            
        except (InvalidCheckpointError, CheckpointError):
            raise
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            raise CheckpointError(f"Failed to load checkpoint: {e}") from e


class AgentRecreator:
    """Recreates agents from checkpoint data."""
    
    @staticmethod
    def restore_agent_message_histories(agents: List[Any], chat_manager: Any) -> None:
        """
        Restore _oai_messages for all agents after they are all created.
        
        This must be done after all agents and manager are created since 
        _oai_messages contains references to other agents.
        
        Args:
            agents: List of recreated agents
            chat_manager: Recreated chat manager
        """
        logger.info("🔄 Restoring agent message histories (_oai_messages)...")
        
        # Create agent lookup by name
        agent_lookup = {agent.name: agent for agent in agents}
        agent_lookup[chat_manager.name] = chat_manager  # Add manager to lookup
        
        restored_count = 0
        
        for agent in agents:
            if hasattr(agent, '_checkpoint_oai_messages_data'):
                oai_messages_data = agent._checkpoint_oai_messages_data
                
                # Restore _oai_messages with proper agent references
                for partner_name, messages in oai_messages_data.items():
                    if partner_name in agent_lookup:
                        partner_agent = agent_lookup[partner_name]
                        
                        # Ensure the partner exists in agent's _oai_messages
                        if partner_agent not in agent._oai_messages:
                            agent._oai_messages[partner_agent] = []
                        
                        # Restore the message history
                        agent._oai_messages[partner_agent] = messages.copy()
                        restored_count += 1
                    else:
                        logger.warning(f"⚠️ Partner agent '{partner_name}' not found for {agent.name}")
                
                # Clean up temporary data
                delattr(agent, '_checkpoint_oai_messages_data')
        
        logger.info(f"✅ Restored {restored_count} conversation histories across all agents")
    
    @staticmethod
    def recreate_agents_from_checkpoint(checkpoint_data: Dict[str, Any]) -> List[Any]:
        """
        Recreate all agents from checkpoint data.
        
        Args:
            checkpoint_data: Loaded checkpoint data
            
        Returns:
            List of recreated agents
            
        Raises:
            RestorationError: If agent recreation fails or required fields are missing
        """
        logger.info("🔧 Recreating agents from checkpoint...")
        
        try:
            # Validate that agent_states exists
            assert 'agent_states' in checkpoint_data, "Missing 'agent_states' in checkpoint data"
            agent_states = checkpoint_data['agent_states']
            
            agents = []
            
            # Import AG2 components (done here to avoid circular imports)
            from autogen import ConversableAgent
            
            for agent_name, agent_state in agent_states.items():
                if agent_name == 'chat_manager':
                    continue  # Skip manager, will be handled separately
                
                logger.info(f"🤖 Recreating agent: {agent_name}")
                
                # Assert required fields for agent restoration
                required_fields = ['name', 'system_message', 'human_input_mode', '_max_consecutive_auto_reply', 'description']
                for field in required_fields:
                    assert field in agent_state, f"Missing required field '{field}' for agent '{agent_name}'"
                
                # Assert LLM config exists and has required fields
                assert 'llm_config' in agent_state, f"Missing 'llm_config' for agent '{agent_name}'"
                checkpoint_llm_config = agent_state['llm_config']
                
                if checkpoint_llm_config is not None:
                    # Validate LLM config has essential fields
                    required_llm_fields = ['model']
                    for field in required_llm_fields:
                        assert field in checkpoint_llm_config, f"Missing required LLM config field '{field}' for agent '{agent_name}'"
                    
                    restored_llm_config = _build_llm_config_from_checkpoint(checkpoint_llm_config)
                    logger.info(f"?? Restored LLM config for {agent_name} with OpenAI API key")
                else:
                    raise RestorationError(f"LLM config is None for agent '{agent_name}' - cannot restore")
                
                # Handle code execution configuration
                checkpoint_code_config = agent_state.get('code_execution_config')
                
                # Convert checkpoint format to ConversableAgent format
                if checkpoint_code_config is None:
                    # No code execution config in checkpoint - don't pass the parameter
                    restored_code_config = None
                    should_omit_code_config = True
                elif isinstance(checkpoint_code_config, dict):
                    if checkpoint_code_config.get('enabled') is False:
                        # Convert {"enabled": false} to False for ConversableAgent
                        restored_code_config = False
                        should_omit_code_config = False
                    elif 'work_dir' in checkpoint_code_config and 'use_docker' in checkpoint_code_config:
                        # Use full config as-is (work_dir, use_docker, etc.)
                        restored_code_config = checkpoint_code_config
                        should_omit_code_config = False
                    else:
                        # Other dict formats - pass through as-is
                        restored_code_config = checkpoint_code_config
                        should_omit_code_config = False
                else:
                    # Other formats - pass through as-is
                    restored_code_config = checkpoint_code_config
                    should_omit_code_config = False
                
                # Handle termination message function restoration
                termination_pattern = agent_state.get('termination_pattern')
                if termination_pattern == 'SOLUTION_FOUND':
                    # Restore the SOLUTION_FOUND termination function
                    is_termination_function = lambda msg: "SOLUTION_FOUND" in (msg.get("content", "") or "")
                    logger.info(f"🎯 Restored SOLUTION_FOUND termination pattern for {agent_name}")
                elif termination_pattern == 'custom':
                    # For custom patterns, we can't restore the exact function, so don't set it
                    # ConversableAgent will use its default termination logic
                    logger.warning(f"⚠️ Agent {agent_name} had custom termination pattern - using default AG2 termination")
                    is_termination_function = None  # Let ConversableAgent use default
                elif termination_pattern is None:
                    # Use default AG2 termination behavior (responds to "TERMINATE")
                    # Don't set is_termination_msg parameter, let ConversableAgent use its default
                    is_termination_function = None  # Let ConversableAgent use default
                else:
                    # Unknown termination pattern - use default
                    logger.warning(f"⚠️ Unknown termination pattern '{termination_pattern}' for {agent_name} - using default")
                    is_termination_function = None
                
                # Prepare agent creation parameters
                agent_params = {
                    'name': agent_state['name'],
                    'system_message': agent_state['system_message'],
                    'llm_config': restored_llm_config,
                    'human_input_mode': agent_state['human_input_mode'],  # No default - assert ensures it exists
                    'max_consecutive_auto_reply': agent_state['_max_consecutive_auto_reply'],  # No default - assert ensures it exists
                    'description': agent_state['description']  # No default - assert ensures it exists
                }
                
                # Only include is_termination_msg if we have a custom function to set
                if is_termination_function is not None:
                    agent_params['is_termination_msg'] = is_termination_function
                
                # Only include code_execution_config if it should be explicitly set
                if not should_omit_code_config:
                    agent_params['code_execution_config'] = restored_code_config
                
                # Recreate agent with restored configuration - use exact values from checkpoint
                agent = ConversableAgent(**agent_params)
                
                # Store _oai_messages data temporarily (will be restored after all agents are created)
                if '_oai_messages' in agent_state:
                    agent._checkpoint_oai_messages_data = agent_state['_oai_messages']
                
                agents.append(agent)
                logger.info(f"✅ Agent {agent_name} recreated successfully")
            
            logger.info(f"✅ Recreated {len(agents)} agents from checkpoint")
            return agents
            
        except AssertionError as e:
            logger.error(f"Checkpoint validation failed: {e}")
            raise RestorationError(f"Checkpoint validation failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to recreate agents: {e}")
            raise RestorationError(f"Failed to recreate agents: {e}") from e


class ConversationContinuator:
    """Continues conversations from checkpoints using AG2 components."""
    
    def __init__(self, loader: Optional[CheckpointLoader] = None, 
                 recreator: Optional[AgentRecreator] = None):
        self.loader = loader or CheckpointLoader()
        self.recreator = recreator or AgentRecreator()
    
    def continue_from_checkpoint(self, checkpoint_file: Union[str, Path], 
                               max_rounds: int = 10) -> bool:
        """
        Continue conversation from checkpoint.
        
        Args:
            checkpoint_file: Path to checkpoint file
            max_rounds: Maximum additional conversation rounds
            
        Returns:
            True if continuation was successful, False otherwise
            
        Raises:
            InvalidCheckpointError: If checkpoint is invalid
            RestorationError: If restoration fails
            CheckpointError: If continuation fails
        """
        logger.info("=== Checkpoint Continuation ===")
        logger.info(f"📄 Checkpoint file: {Path(checkpoint_file).name}")
        logger.info(f"🔢 Max rounds: {max_rounds}")
        
        try:
            # Load checkpoint
            checkpoint_data = self.loader.load_checkpoint(checkpoint_file)
            
            # Recreate agents
            agents = self.recreator.recreate_agents_from_checkpoint(checkpoint_data)
            
            # Import AG2 components
            from autogen.agentchat.groupchat import GroupChat
            
            # Import checkpoint system wrapper
            from .wrappers import CheckpointingGroupChatManager
            
            # Recreate GroupChat
            assert 'groupchat_state' in checkpoint_data, "Missing 'groupchat_state' in checkpoint data"
            assert 'messages' in checkpoint_data['groupchat_state'], "Missing 'messages' in groupchat_state"
            
            groupchat = GroupChat(
                agents=agents,
                messages=checkpoint_data['groupchat_state']['messages'],
                max_round=checkpoint_data['groupchat_state'].get('max_round', max_rounds + checkpoint_data['current_round'])
            )
            
            # Validate manager state exists
            assert 'manager_state' in checkpoint_data, "Missing 'manager_state' in checkpoint data"
            manager_state = checkpoint_data['manager_state']
            
            # Assert required fields for manager restoration
            required_manager_fields = ['name', 'system_message', 'human_input_mode', '_max_consecutive_auto_reply']
            for field in required_manager_fields:
                assert field in manager_state, f"Missing required field '{field}' for chat manager"
            
            # Reconstruct LLM config for chat manager
            
            assert 'llm_config' in manager_state, "Missing 'llm_config' for chat manager"
            checkpoint_manager_llm_config = manager_state['llm_config']
            
            if checkpoint_manager_llm_config is not None:
                # Validate LLM config has essential fields
                    required_llm_fields = ['model']
                for field in required_llm_fields:
                    assert field in checkpoint_manager_llm_config, f"Missing required LLM config field '{field}' for chat manager"
                
                restored_manager_llm_config = _build_llm_config_from_checkpoint(checkpoint_manager_llm_config)
                logger.info("?? Restored LLM config for chat manager with OpenAI API key")
            else:
                raise RestorationError("LLM config is None for chat manager - cannot restore")
            
            # Create a checkpoint manager for the continued session in a separate directory
            from .core import create_checkpoint_manager
            from datetime import datetime
            
            checkpoint_path = Path(checkpoint_file)
            original_session_dir = checkpoint_path.parent.parent  # Go up from checkpoints/ to session dir
            
            # Create continuation directory with timestamp
            continuation_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            continuation_dir_name = f"continuation_{continuation_timestamp}"
            continuation_session_dir = original_session_dir / continuation_dir_name
            continuation_session_dir.mkdir(exist_ok=True)
            
            logger.info(f"📁 Creating continuation session directory: {continuation_dir_name}")
            logger.info(f"📂 Continuation checkpoints will be saved to: {continuation_session_dir / 'checkpoints'}")
            
            continuation_checkpoint_manager = create_checkpoint_manager(continuation_session_dir)
            
            # Save continuation metadata
            continuation_metadata = {
                "continuation_timestamp": continuation_timestamp,
                "original_session_dir": str(original_session_dir),
                "original_checkpoint_file": str(checkpoint_path.name),
                "original_checkpoint_id": checkpoint_data.get('checkpoint_id'),
                "original_round": checkpoint_data.get('current_round'),
                "max_additional_rounds": max_rounds,
                "continuation_started_at": datetime.now().isoformat()
            }
            
            metadata_file = continuation_session_dir / "continuation_metadata.json"
            import json
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(continuation_metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Continuation metadata saved to: {metadata_file.name}")
            
            # Prepare manager creation parameters
            manager_params = {
                'checkpoint_manager': continuation_checkpoint_manager,
                'groupchat': groupchat,
                'name': manager_state['name'],
                'system_message': manager_state['system_message'],
                'llm_config': restored_manager_llm_config,
                'human_input_mode': manager_state['human_input_mode'],  # No default - assert ensures it exists
                'max_consecutive_auto_reply': manager_state['_max_consecutive_auto_reply'],  # No default - assert ensures it exists
                'description': manager_state.get('description')  # This field is optional
            }
            
            # Restore termination pattern if present
            termination_pattern = manager_state.get('termination_pattern')
            if termination_pattern == 'SOLUTION_FOUND':
                manager_params['is_termination_msg'] = lambda msg: "SOLUTION_FOUND" in (msg.get("content", "") or "")
                logger.info("🔧 Restored SOLUTION_FOUND termination pattern for manager")
            elif termination_pattern == 'custom':
                logger.warning("⚠️ Custom termination pattern detected for manager but cannot be restored automatically")
                # Keep default behavior if we can't restore the custom pattern
            # If termination_pattern is None, use default behavior (no is_termination_msg parameter)
            
            # Recreate chat manager with checkpointing - use exact values from checkpoint
            chat_manager = CheckpointingGroupChatManager(**manager_params)
            
            # Restore agent message histories
            self.recreator.restore_agent_message_histories(agents, chat_manager)
            
            logger.info("🚀 Starting conversation continuation...")
            
            # Continue the conversation using the loaded state
            success, termination_reason = chat_manager.continue_from_loaded_state(
                max_additional_rounds=max_rounds
            )
            
            if success:
                logger.info("✅ Conversation continuation completed successfully!")
                logger.info(f"📁 Continuation session saved to: {continuation_session_dir}")
                logger.info(f"📂 New checkpoints location: {continuation_session_dir / 'checkpoints'}")
                if termination_reason:
                    logger.info(f"🔚 Termination reason: {termination_reason}")
                return True
            else:
                logger.error("❌ Conversation continuation failed")
                return False
            
        except AssertionError as e:
            logger.error(f"Checkpoint validation failed during continuation: {e}")
            raise RestorationError(f"Checkpoint validation failed: {e}") from e
        except (InvalidCheckpointError, RestorationError, CheckpointError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error during continuation: {e}")
            raise CheckpointError(f"Continuation failed: {e}") from e


class CheckpointRestorer:
    """
    Main class for checkpoint restoration and continuation.
    
    Provides a high-level interface for loading checkpoints and continuing conversations.
    """
    
    def __init__(self):
        self.validator = CheckpointValidator()
        self.loader = CheckpointLoader(self.validator)
        self.recreator = AgentRecreator()
        self.continuator = ConversationContinuator(self.loader, self.recreator)
    
    def validate_checkpoint_file(self, checkpoint_file: Union[str, Path]) -> None:
        """Validate checkpoint file for restoration compatibility."""
        return self.validator.validate_checkpoint_file(Path(checkpoint_file))
    
    def load_checkpoint(self, checkpoint_file: Union[str, Path]) -> Dict[str, Any]:
        """Load and validate checkpoint data."""
        return self.loader.load_checkpoint(checkpoint_file)
    
    def continue_conversation(self, checkpoint_file: Union[str, Path], 
                            max_rounds: int = 10) -> bool:
        """Continue conversation from checkpoint."""
        return self.continuator.continue_from_checkpoint(checkpoint_file, max_rounds)
    
    @staticmethod
    def create_restorer() -> 'CheckpointRestorer':
        """Factory method to create a CheckpointRestorer instance."""
        return CheckpointRestorer()
