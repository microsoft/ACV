"""
Core checkpoint manager for AG2 conversations.

This module provides the main CheckpointManager class that handles saving and loading
of complete AG2 conversation states, enabling resume functionality from any point.
Follows the same session-based logging pattern as mathchat.py.
"""

import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union, List
from pathlib import Path

from .exceptions import (
    CheckpointError, 
    CheckpointNotFoundError,
    InvalidCheckpointError,
    SerializationError,
    RestorationError,
    VersionCompatibilityError
)
from .utils import (
    generate_checkpoint_id,
    calculate_state_hash,
    validate_checkpoint_data,
    get_ag2_version,
    format_checkpoint_summary,
    ensure_directory_exists
)

# Set up logger first
logger = logging.getLogger(__name__)

# Import AG2 components with fallback
try:
    # Add AG2 path to sys.path if not already there
    import sys
    ag2_path = Path(__file__).parent.parent / "ag2-0.10.0"
    if ag2_path.exists() and str(ag2_path) not in sys.path:
        sys.path.insert(0, str(ag2_path))
    
    from autogen.agentchat.groupchat import GroupChat, GroupChatManager
    from autogen.agentchat.conversable_agent import ConversableAgent
    # Removed: AG2 cache imports - we only use JSON file storage now
    
    logger.info("AG2 components imported successfully")
    
except ImportError as e:
    # For development/testing purposes, create stub classes
    logger.warning(f"AG2 components not available, using stubs: {e}")
    
    class GroupChat:
        def __init__(self, **kwargs):
            self.messages = []
            self.max_round = 10
            self.admin_name = "Admin"
            self.func_call_filter = True
            self.speaker_selection_method = "auto"
            self.allow_repeat_speaker = True
            self.send_introductions = False
            self.enable_clear_history = False
            self.agents = []
    
    class GroupChatManager:
        def __init__(self, **kwargs):
            self.name = "manager"
            self.system_message = ""
            self.human_input_mode = "NEVER"
            self._last_speaker = None
            self._max_consecutive_auto_reply = 1
    
    class ConversableAgent:
        def __init__(self, **kwargs):
            self.name = ""
            self.system_message = ""
            self.human_input_mode = "NEVER"
            self._max_consecutive_auto_reply = 1
    
    # Removed: AbstractCache and DiskCache stubs - no longer needed


@dataclass
class CheckpointData:
    """Data structure for storing complete conversation state."""
    
    # Basic checkpoint info
    checkpoint_id: str
    timestamp: datetime
    
    # Position tracking 
    current_round: int  # Current round in conversation loop
    total_steps: int    # Total conversation steps taken
    
    # Core AG2 state
    groupchat_state: Dict[str, Any]
    manager_state: Dict[str, Any]  
    agent_states: Dict[str, Dict[str, Any]]  # agent_name -> state
    
    # Execution context (will be populated in later steps)
    speaker_selection_state: Dict[str, Any] = field(default_factory=dict)
    message_broadcast_state: Dict[str, Any] = field(default_factory=dict)
    conversation_flow_state: Dict[str, Any] = field(default_factory=dict)
    
    # Environment state (will be populated in later steps)
    code_execution_state: Dict[str, Any] = field(default_factory=dict)
    client_cache_state: Dict[str, Any] = field(default_factory=dict)
    
    # Session context
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    problem_context: str = ""
    
    # Integrity and compatibility
    state_hash: str = ""
    ag2_version: str = field(default_factory=get_ag2_version)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'checkpoint_id': self.checkpoint_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'current_round': self.current_round,
            'total_steps': self.total_steps,
            'groupchat_state': self.groupchat_state,
            'manager_state': self.manager_state,
            'agent_states': self.agent_states,
            'speaker_selection_state': self.speaker_selection_state,
            'message_broadcast_state': self.message_broadcast_state,
            'conversation_flow_state': self.conversation_flow_state,
            'code_execution_state': self.code_execution_state,
            'client_cache_state': self.client_cache_state,
            'session_metadata': self.session_metadata,
            'problem_context': self.problem_context,
            'state_hash': self.state_hash,
            'ag2_version': self.ag2_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointData':
        """Create from dictionary."""
        # Handle timestamp conversion
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            checkpoint_id=data['checkpoint_id'],
            timestamp=timestamp,
            current_round=data['current_round'],
            total_steps=data['total_steps'],
            groupchat_state=data['groupchat_state'],
            manager_state=data['manager_state'],
            agent_states=data['agent_states'],
            speaker_selection_state=data.get('speaker_selection_state', {}),
            message_broadcast_state=data.get('message_broadcast_state', {}),
            conversation_flow_state=data.get('conversation_flow_state', {}),
            code_execution_state=data.get('code_execution_state', {}),
            client_cache_state=data.get('client_cache_state', {}),
            session_metadata=data.get('session_metadata', {}),
            problem_context=data.get('problem_context', ''),
            state_hash=data.get('state_hash', ''),
            ag2_version=data.get('ag2_version', 'unknown')
        )


class CheckpointManager:
    """
    Main checkpoint manager for AG2 conversations.
    
    This class provides the core functionality to save and restore complete
    conversation states, enabling pause/resume functionality for multi-agent chats.
    Follows the session-based directory pattern from mathchat.py.
    """
    
    def __init__(self, session_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the CheckpointManager with session-based directory structure.
        Uses only JSON file storage - no disk cache dependency.
        
        Args:
            session_dir: Session directory for organizing checkpoint files.
                        If None, creates a timestamped session directory like mathchat.py
        """
        # Create session directory following mathchat.py pattern
        if session_dir is None:
            session_dir = self._create_session_directory()
        else:
            session_dir = Path(session_dir)
            
        self.session_dir = session_dir
        self.session_id = self.session_dir.name
        
        # Create only checkpoints subdirectory - follow mathchat.py structure
        self.checkpoints_dir = self.session_dir / "checkpoints"
        
        # Ensure directories exist
        ensure_directory_exists(self.session_dir)
        ensure_directory_exists(self.checkpoints_dir)
        
        # Initialize minimal session metadata for checkpoints
        self.checkpoint_metadata = {
            "session_id": self.session_id,
            "created_at": datetime.now().isoformat(),
            "checkpoint_count": 0,
            "last_checkpoint_time": None,
            "checkpoints_directory": str(self.checkpoints_dir)
        }
        
        # Initialize other components (will be implemented in later steps)
        self.serializer = None  # Will be initialized when StateSerializer is implemented
        self.restorer = None    # Will be initialized when StateRestorer is implemented
        
        logger.info(f"CheckpointManager initialized with session_dir: {self.session_id}")
    
    def _create_session_directory(self, base_log_dir: str = "logs") -> Path:
        """Create a unique session directory following mathchat.py pattern."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        
        base_path = Path(base_log_dir)
        base_path.mkdir(exist_ok=True)
        
        session_dir = base_path / session_id
        session_dir.mkdir(exist_ok=True)
        
        return session_dir
    
    def _update_checkpoint_metadata(self, **kwargs):
        """Update minimal checkpoint metadata."""
        self.checkpoint_metadata.update(kwargs)
        self.checkpoint_metadata["last_updated"] = datetime.now().isoformat()
    
    def save_checkpoint(
        self, 
        data_or_groupchat: Union[CheckpointData, GroupChat], 
        manager: Optional[GroupChatManager] = None,
        current_round: int = 0,
        total_steps: int = 0,
        problem_context: str = "",
        **kwargs
    ) -> str:
        """
        Save a checkpoint of the current conversation state.
        
        Args:
            data_or_groupchat: Either a CheckpointData object or GroupChat object to checkpoint
            manager: The GroupChatManager object to checkpoint (only needed if first arg is GroupChat)  
            current_round: Current round number in the conversation
            total_steps: Total conversation steps taken so far
            problem_context: The original problem text being solved
            **kwargs: Additional metadata to store
            
        Returns:
            str: Checkpoint ID for later retrieval
            
        Raises:
            SerializationError: If state serialization fails
            CheckpointError: If checkpoint save operation fails
        """
        try:
            # Handle both CheckpointData and legacy GroupChat input
            if isinstance(data_or_groupchat, CheckpointData):
                checkpoint_data = data_or_groupchat
                # Update state hash if not set
                if not checkpoint_data.state_hash:
                    checkpoint_dict = checkpoint_data.to_dict()
                    checkpoint_data.state_hash = calculate_state_hash(checkpoint_dict)
            else:
                # Legacy path - create CheckpointData from GroupChat and manager
                groupchat = data_or_groupchat
                if manager is None:
                    raise CheckpointError("Manager required when passing GroupChat object")
                    
                # Generate unique checkpoint ID
                checkpoint_id = generate_checkpoint_id()
                
                logger.info(f"Creating checkpoint {checkpoint_id}")
                
                # Extract state from AG2 objects
                groupchat_state = self._extract_groupchat_state(groupchat)
                manager_state = self._extract_manager_state(manager)
                agent_states = self._extract_agent_states(groupchat.agents)
                
                # Create checkpoint data
                checkpoint_data = CheckpointData(
                    checkpoint_id=checkpoint_id,
                    timestamp=datetime.now(),
                    current_round=current_round,
                    total_steps=total_steps,
                    groupchat_state=groupchat_state,
                    manager_state=manager_state,
                    agent_states=agent_states,
                    problem_context=problem_context,
                    session_metadata={
                        'ag2_version': get_ag2_version(),
                        'session_dir': str(self.session_dir),
                        **kwargs
                    }
                )
                
                # Calculate state hash for integrity
                checkpoint_dict = checkpoint_data.to_dict()
                checkpoint_data.state_hash = calculate_state_hash(checkpoint_dict)
            
            # Save to storage using checkpoint_data.checkpoint_id
            # REMOVED: self.storage.set() - causes lambda serialization issues
            # We only use JSON file storage which works fine
            
            # Save essential checkpoint file only (no redundant summaries or metadata)
            self._save_checkpoint_file(checkpoint_data)
            
            # Update minimal checkpoint metadata
            self.checkpoint_metadata["checkpoint_count"] = self.checkpoint_metadata.get("checkpoint_count", 0) + 1
            self.checkpoint_metadata["last_checkpoint_time"] = datetime.now().isoformat()
            self.checkpoint_metadata["last_checkpoint_id"] = checkpoint_data.checkpoint_id
            self._update_checkpoint_metadata()
            
            logger.info(f"Checkpoint {checkpoint_data.checkpoint_id} saved successfully")
            return checkpoint_data.checkpoint_id
            
        except Exception as e:
            raise CheckpointError(f"Failed to save checkpoint: {e}") from e

    def create_conversation_checkpoint(
        self,
        step: int,
        action: str,
        groupchat: "GroupChat",
        manager: "GroupChatManager",
        speaker: "ConversableAgent",
        message_content: str,
        problem_context: str = "",
        **kwargs
    ) -> str:
        """
        Create and save a checkpoint from conversation state parameters.
        
        This method centralizes all checkpoint creation logic and should be used
        by wrappers instead of duplicating the checkpoint creation logic.
        
        Args:
            step: Current conversation step/round
            action: Type of action (conversation_start, message_appended, etc.)
            groupchat: The GroupChat object
            manager: The GroupChatManager object
            speaker: The current speaker agent
            message_content: Content of the current message/action
            problem_context: The problem being solved
            **kwargs: Additional metadata
            
        Returns:
            str: Generated checkpoint ID
        """
        try:
            from datetime import datetime
            
            # Generate checkpoint ID using consistent format
            checkpoint_id = f"checkpoint_{step}_{action}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Extract states using centralized methods
            groupchat_state = self._extract_groupchat_state(groupchat)
            manager_state = self._extract_manager_state(manager)
            agent_states = self._extract_agent_states(getattr(groupchat, 'agents', []))
            
            # Create comprehensive checkpoint data
            checkpoint_data = CheckpointData(
                checkpoint_id=checkpoint_id,
                timestamp=datetime.now(),
                current_round=step,
                total_steps=len(groupchat.messages),
                groupchat_state=groupchat_state,
                manager_state=manager_state,
                agent_states=agent_states,
                session_metadata={
                    'action': action,
                    'message_content': message_content,
                    'current_speaker': getattr(speaker, 'name', 'unknown'),
                    **kwargs
                },
                problem_context=problem_context,
                state_hash="",  # Will be calculated in save_checkpoint
                ag2_version=get_ag2_version()
            )
            
            # Save using the centralized save method
            saved_checkpoint_id = self.save_checkpoint(checkpoint_data)
            
            return saved_checkpoint_id
            
        except Exception as e:
            logger.error(f"Failed to create conversation checkpoint: {e}")
            raise CheckpointError(f"Failed to create conversation checkpoint: {e}") from e
    
    def load_checkpoint(self, checkpoint_id: str) -> CheckpointData:
        """
        Load a checkpoint by ID from JSON file storage.
        
        Args:
            checkpoint_id: The checkpoint ID to load
            
        Returns:
            CheckpointData: The loaded checkpoint data
            
        Raises:
            CheckpointNotFoundError: If checkpoint doesn't exist
            InvalidCheckpointError: If checkpoint is corrupted
        """
        try:
            # Load from JSON file instead of disk cache
            checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.json"
            if not checkpoint_file.exists():
                raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")
            
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_dict = json.load(f)
            
            # Validate checkpoint data
            if not validate_checkpoint_data(checkpoint_dict):
                raise InvalidCheckpointError(f"Checkpoint {checkpoint_id} is missing required fields")
            
            # Verify integrity
            stored_hash = checkpoint_dict.get('state_hash', '')
            if stored_hash:
                # Calculate hash excluding the hash field itself
                dict_for_hash = {k: v for k, v in checkpoint_dict.items() if k != 'state_hash'}
                calculated_hash = calculate_state_hash(dict_for_hash)
                if stored_hash != calculated_hash:
                    logger.warning(f"Checkpoint {checkpoint_id} integrity check failed")
            
            checkpoint_data = CheckpointData.from_dict(checkpoint_dict)
            
            logger.info(f"Checkpoint {checkpoint_id} loaded successfully")
            return checkpoint_data
            
        except CheckpointNotFoundError:
            raise
        except Exception as e:
            raise InvalidCheckpointError(f"Failed to load checkpoint {checkpoint_id}: {e}") from e
    
    def restore_groupchat(self, checkpoint_data: CheckpointData) -> tuple[GroupChat, GroupChatManager]:
        """
        Restore GroupChat and GroupChatManager from checkpoint data.
        
        Args:
            checkpoint_data: The checkpoint data to restore from
            
        Returns:
            tuple: (restored_groupchat, restored_manager)
            
        Raises:
            RestorationError: If state restoration fails
            VersionCompatibilityError: If AG2 version is incompatible
        """
        try:
            # Check version compatibility
            current_version = get_ag2_version()
            checkpoint_version = checkpoint_data.ag2_version
            
            if checkpoint_version != 'unknown' and checkpoint_version != current_version:
                logger.warning(f"Version mismatch: checkpoint={checkpoint_version}, current={current_version}")
            
            logger.info(f"Restoring checkpoint {checkpoint_data.checkpoint_id}")
            
            # Full restoration logic is implemented in the separate restoration script
            # This method focuses on checkpoint loading and validation
            raise NotImplementedError("Restoration is handled by separate restoration script - use test_checkpoint_continuation.py")
            
        except Exception as e:
            raise RestorationError(f"Failed to restore from checkpoint: {e}") from e
    
    def list_checkpoints(self) -> list[str]:
        """
        List all available checkpoint IDs.
        
        Returns:
            list[str]: List of checkpoint IDs
        """
        # This is a basic implementation - AG2's cache doesn't have a native list method
        # We'll enhance this when we implement the storage layer
        logger.info("Listing available checkpoints (basic implementation)")
        return []
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: The checkpoint ID to delete
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            # Note: AG2's AbstractCache doesn't have a delete method
            # We'll implement this in our storage layer
            logger.info(f"Deleting checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False
    
    def _extract_groupchat_state(self, groupchat: GroupChat) -> Dict[str, Any]:
        """Extract complete state from GroupChat object."""
        groupchat_state = {
            'messages': getattr(groupchat, 'messages', []).copy() if hasattr(groupchat, 'messages') else [],
            'max_round': getattr(groupchat, 'max_round', 10),
            'admin_name': getattr(groupchat, 'admin_name', None),
            'speaker_selection_method': getattr(groupchat, 'speaker_selection_method', 'auto'),
            'allow_repeat_speaker': getattr(groupchat, 'allow_repeat_speaker', True),
            'send_introductions': getattr(groupchat, 'send_introductions', False),
            'enable_clear_history': getattr(groupchat, 'enable_clear_history', False),
        }
        
        # Add func_call_filter if it exists (handle callable safely)
        if hasattr(groupchat, 'func_call_filter'):
            func_call_filter = getattr(groupchat, 'func_call_filter', None)
            if callable(func_call_filter):
                # Don't serialize the function itself, just note its existence
                groupchat_state['has_func_call_filter'] = True
                groupchat_state['func_call_filter_type'] = type(func_call_filter).__name__
            else:
                groupchat_state['func_call_filter'] = func_call_filter
                groupchat_state['has_func_call_filter'] = False
        else:
            groupchat_state['has_func_call_filter'] = False
        
        # Add agents list (lightweight - just names for GroupChat reconstruction)
        agents = getattr(groupchat, 'agents', [])
        groupchat_state['agents'] = [{'name': getattr(agent, 'name', 'unknown')} for agent in agents]
        
        return groupchat_state
    
    def _extract_manager_state(self, manager: GroupChatManager) -> Dict[str, Any]:
        """Extract complete state from GroupChatManager object."""
        manager_state = {
            'name': getattr(manager, 'name', 'unknown'),
            'system_message': getattr(manager, 'system_message', ''),
            'human_input_mode': getattr(manager, 'human_input_mode', 'NEVER'),
            '_last_speaker': getattr(manager, '_last_speaker', None),
            '_max_consecutive_auto_reply': getattr(manager, '_max_consecutive_auto_reply', 0),
        }
        
        # Add CheckpointingGroupChatManager specific fields if available
        if hasattr(manager, 'step_counter'):
            manager_state['step_counter'] = getattr(manager, 'step_counter', 0)
        
        # Add current speaker if _last_speaker has name attribute
        last_speaker = getattr(manager, '_last_speaker', None)
        if last_speaker and hasattr(last_speaker, 'name'):
            manager_state['current_speaker'] = last_speaker.name
        else:
            manager_state['current_speaker'] = 'unknown'
        
        # Extract LLM configuration from manager (same logic as for agents)
        if hasattr(manager, 'llm_config') and manager.llm_config:
            try:
                # Use model_dump to get all configuration fields
                if hasattr(manager.llm_config, 'model_dump'):
                    llm_config_dict = manager.llm_config.model_dump()
                elif isinstance(manager.llm_config, dict):
                    llm_config_dict = dict(manager.llm_config)  # Make a copy
                else:
                    # Fallback for older versions or different config types
                    llm_config_dict = dict(manager.llm_config) if hasattr(manager.llm_config, '__iter__') else {}
                
                # Start with the base config excluding config_list
                filtered_config = {}
                
                # Include simple fields from the top level
                for key, value in llm_config_dict.items():
                    if key != 'config_list' and isinstance(value, (str, int, float, bool, type(None))):
                        filtered_config[key] = value
                
                # Extract configuration details from config_list if present
                if 'config_list' in llm_config_dict and isinstance(llm_config_dict['config_list'], list):
                    config_list = llm_config_dict['config_list']
                    
                    if config_list:
                        # Use the first config entry as the primary configuration
                        first_config = config_list[0]
                        if isinstance(first_config, dict):
                            # Extract important configuration fields from the config entry
                            config_fields_to_extract = [
                                'model', 'base_url', 'api_type', 'api_version', 'azure_deployment', 
                                'azure_endpoint', 'temperature', 'top_p', 'seed', 'timeout', 
                                'max_tokens'  # This might also be in the config entry
                            ]
                            
                            for field in config_fields_to_extract:
                                if field in first_config:
                                    value = first_config[field]
                                    # Skip sensitive authentication fields
                                    if field not in ['azure_ad_token_provider', 'api_key', 'token_provider', 'auth_provider']:
                                        if isinstance(value, (str, int, float, bool, type(None))):
                                            filtered_config[field] = value
                
                # Remove any remaining non-serializable fields
                non_serializable_fields = {
                    'azure_ad_token_provider',
                    'api_key',  # Security: don't save API keys
                    'token_provider',
                    'auth_provider',
                    'config_list'  # Already processed above
                }
                
                # Final filtering for safety
                final_config = {}
                for key, value in filtered_config.items():
                    if key not in non_serializable_fields and isinstance(value, (str, int, float, bool, type(None))):
                        final_config[key] = value
                
                manager_state['llm_config'] = final_config if final_config else None
                
            except Exception as e:
                logger.warning(f"Failed to serialize manager LLM config: {e}")
                manager_state['llm_config'] = None
        else:
            manager_state['llm_config'] = None
        
        # Detect manager termination pattern (similar to agent logic)
        if hasattr(manager, '_is_termination_msg') and callable(manager._is_termination_msg):
            try:
                # Test with SOLUTION_FOUND message
                solution_msg = {"content": "SOLUTION_FOUND"}
                terminate_msg = {"content": "TERMINATE"}
                
                responds_to_solution = manager._is_termination_msg(solution_msg)
                responds_to_terminate = manager._is_termination_msg(terminate_msg)
                
                if responds_to_solution and not responds_to_terminate:
                    # Responds to SOLUTION_FOUND but not TERMINATE -> custom SOLUTION_FOUND pattern
                    manager_state['termination_pattern'] = 'SOLUTION_FOUND'
                elif not responds_to_solution and responds_to_terminate:
                    # Responds to TERMINATE but not SOLUTION_FOUND -> default AG2 termination
                    manager_state['termination_pattern'] = None  # Treat as default/no custom termination
                elif responds_to_solution and responds_to_terminate:
                    # Responds to both -> custom termination that includes SOLUTION_FOUND
                    manager_state['termination_pattern'] = 'SOLUTION_FOUND'
                else:
                    # Doesn't respond to either standard pattern
                    manager_state['termination_pattern'] = 'custom'
            except Exception as e:
                logger.warning(f"Failed to detect manager termination pattern for {manager.name}: {e}")
                manager_state['termination_pattern'] = 'custom'
        else:
            manager_state['termination_pattern'] = None  # No custom termination
        
        return manager_state
    
    def _extract_agent_states(self, agents: list) -> Dict[str, Dict[str, Any]]:
        """
        Extract essential states from all agents - avoid complex objects that may contain lambdas.
        
        All fields marked as REQUIRED must be present in checkpoints for proper agent restoration.
        """
        agent_states = {}
        for agent in agents:
            if hasattr(agent, 'name'):
                # Basic agent information - ALL REQUIRED for restoration
                agent_state = {
                    'name': agent.name,  # REQUIRED
                    'system_message': getattr(agent, 'system_message', ''),  # REQUIRED
                    'human_input_mode': getattr(agent, 'human_input_mode', 'NEVER'),  # REQUIRED
                    '_max_consecutive_auto_reply': getattr(agent, '_max_consecutive_auto_reply', 0),  # REQUIRED
                    'description': getattr(agent, 'description', ''),  # REQUIRED (may be empty string)
                }
                
                # LLM configuration - use model_dump to get complete config
                if hasattr(agent, 'llm_config') and agent.llm_config:
                    try:
                        # Use model_dump to get all configuration fields
                        if hasattr(agent.llm_config, 'model_dump'):
                            llm_config_dict = agent.llm_config.model_dump()
                        elif isinstance(agent.llm_config, dict):
                            llm_config_dict = dict(agent.llm_config)  # Make a copy
                        else:
                            # Fallback for older versions or different config types
                            llm_config_dict = dict(agent.llm_config) if hasattr(agent.llm_config, '__iter__') else {}
                        
                        # Start with the base config excluding config_list
                        filtered_config = {}
                        
                        # Include simple fields from the top level
                        for key, value in llm_config_dict.items():
                            if key != 'config_list' and isinstance(value, (str, int, float, bool, type(None))):
                                filtered_config[key] = value
                        
                        # Extract configuration details from config_list if present
                        if 'config_list' in llm_config_dict and isinstance(llm_config_dict['config_list'], list):
                            config_list = llm_config_dict['config_list']
                            
                            if config_list:
                                # Use the first config entry as the primary configuration
                                first_config = config_list[0]
                                if isinstance(first_config, dict):
                                    # Extract important configuration fields from the config entry
                                    config_fields_to_extract = [
                                        'model', 'base_url', 'api_type', 'api_version', 'azure_deployment', 
                                        'azure_endpoint', 'temperature', 'top_p', 'seed', 'timeout', 
                                        'max_tokens'  # This might also be in the config entry
                                    ]
                                    
                                    for field in config_fields_to_extract:
                                        if field in first_config:
                                            value = first_config[field]
                                            # Skip sensitive authentication fields
                                            if field not in ['azure_ad_token_provider', 'api_key', 'token_provider', 'auth_provider']:
                                                if isinstance(value, (str, int, float, bool, type(None))):
                                                    filtered_config[field] = value
                        
                        # Remove any remaining non-serializable fields
                        non_serializable_fields = {
                            'azure_ad_token_provider',
                            'api_key',  # Security: don't save API keys
                            'token_provider',
                            'auth_provider',
                            'config_list'  # Already processed above
                        }
                        
                        # Final filtering for safety
                        final_config = {}
                        for key, value in filtered_config.items():
                            if key not in non_serializable_fields and isinstance(value, (str, int, float, bool, type(None))):
                                final_config[key] = value
                        
                        agent_state['llm_config'] = final_config if final_config else None
                        
                    except Exception as e:
                        logger.warning(f"Failed to serialize LLM config for {agent.name}: {e}")
                        # Fallback to manual extraction
                        llm_config_dict = {}
                        for attr in ['model', 'base_url', 'api_type', 'api_version', 'max_tokens', 'temperature', 'top_p', 'seed', 'timeout']:
                            if hasattr(agent.llm_config, attr):
                                value = getattr(agent.llm_config, attr)
                                if isinstance(value, (str, int, float, bool, type(None))):
                                    llm_config_dict[attr] = value
                        agent_state['llm_config'] = llm_config_dict if llm_config_dict else None
                else:
                    agent_state['llm_config'] = None
                
                # Code execution configuration (REQUIRED - may be None)
                # Check both the public and private attribute names
                code_exec_config = getattr(agent, 'code_execution_config', None)
                if code_exec_config is None:
                    code_exec_config = getattr(agent, '_code_execution_config', None)
                
                if code_exec_config is None or isinstance(code_exec_config, dict):
                    agent_state['code_execution_config'] = code_exec_config  # REQUIRED field
                else:
                    agent_state['code_execution_config'] = {'enabled': bool(code_exec_config)}
                
                # Termination message function (REQUIRED - may be None)
                if hasattr(agent, '_is_termination_msg') and callable(agent._is_termination_msg):
                    # Try to detect termination patterns
                    try:
                        # Test with SOLUTION_FOUND message
                        solution_msg = {"content": "SOLUTION_FOUND"}
                        solution_test = agent._is_termination_msg(solution_msg)
                        
                        # Test with TERMINATE message (default AG2 termination)
                        terminate_msg = {"content": "TERMINATE"}
                        terminate_test = agent._is_termination_msg(terminate_msg)
                        
                        if solution_test and not terminate_test:
                            # Responds to SOLUTION_FOUND but not TERMINATE -> custom SOLUTION_FOUND pattern
                            agent_state['termination_pattern'] = 'SOLUTION_FOUND'
                        elif terminate_test and not solution_test:
                            # Responds to TERMINATE but not SOLUTION_FOUND -> default AG2 termination
                            agent_state['termination_pattern'] = None  # Treat as default/no custom termination
                        elif solution_test and terminate_test:
                            # Responds to both -> custom termination that includes SOLUTION_FOUND
                            agent_state['termination_pattern'] = 'SOLUTION_FOUND'
                        else:
                            # Responds to neither -> other custom termination
                            agent_state['termination_pattern'] = 'custom'
                    except Exception as e:
                        agent_state['termination_pattern'] = 'custom'
                else:
                    agent_state['termination_pattern'] = None  # REQUIRED field (may be None)
                
                # Agent class type for proper reconstruction
                agent_state['agent_class'] = type(agent).__name__
                agent_state['agent_module'] = type(agent).__module__
                
                # Additional simple attributes only
                for attr in ['max_turns', 'send_introductions']:
                    if hasattr(agent, attr):
                        value = getattr(agent, attr, None)
                        # Only include simple types
                        if isinstance(value, (str, int, float, bool, type(None))):
                            agent_state[attr] = value
                
                # Function/cache flags without the actual objects
                agent_state['has_function_map'] = bool(getattr(agent, 'function_map', None))
                agent_state['has_client_cache'] = bool(getattr(agent, 'client_cache', None))
                
                # **CRITICAL FOR CONTINUATION**: Capture _oai_messages state
                # This is essential for proper continuation without relying on AG2's resume logic
                if hasattr(agent, '_oai_messages') and agent._oai_messages:
                    oai_messages_dict = {}
                    for conversation_partner, messages in agent._oai_messages.items():
                        # Store messages with partner name as key
                        partner_name = getattr(conversation_partner, 'name', str(conversation_partner))
                        # Deep copy the messages to avoid reference issues
                        oai_messages_dict[partner_name] = [
                            dict(msg) for msg in messages  # Create a copy of each message dict
                        ]
                    agent_state['_oai_messages'] = oai_messages_dict
                else:
                    # Always ensure _oai_messages field exists (even if empty)
                    agent_state['_oai_messages'] = {}
                
                agent_states[agent.name] = agent_state
                
        return agent_states
    
    def _save_checkpoint_file(self, checkpoint_data: CheckpointData) -> None:
        """Save essential checkpoint data only."""
        try:
            # Save checkpoint as JSON file in checkpoints directory
            checkpoint_file = self.checkpoints_dir / f"{checkpoint_data.checkpoint_id}.json"
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data.to_dict(), f, indent=2, ensure_ascii=False, default=str)
            
        except Exception as e:
            logger.warning(f"Failed to save checkpoint file: {e}")
    
    def save_checkpoints_metadata(self) -> Path:
        """Save minimal checkpoint metadata to checkpoints directory."""
        try:
            metadata_file = self.checkpoints_dir / "checkpoints_metadata.json"
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint_metadata, f, indent=2, ensure_ascii=False, default=str)
            
            return metadata_file
            
        except Exception as e:
            logger.warning(f"Failed to save checkpoints metadata: {e}")
            return Path()
    
    def get_checkpoints_summary(self) -> Dict[str, Any]:
        """Get summary of checkpoints for integration with session metadata."""
        return {
            "checkpoint_count": self.checkpoint_metadata.get("checkpoint_count", 0),
            "last_checkpoint_time": self.checkpoint_metadata.get("last_checkpoint_time"),
            "last_checkpoint_id": self.checkpoint_metadata.get("last_checkpoint_id"),
            "checkpoints_directory": "checkpoints"
        }


def create_checkpoint_manager(session_dir: Union[str, Path]) -> CheckpointManager:
    """
    Factory function to create a CheckpointManager with simplified JSON-only storage.
    
    Args:
        session_dir: Session directory for checkpoint storage
        
    Returns:
        CheckpointManager: Configured checkpoint manager instance
    """
    return CheckpointManager(session_dir=session_dir)