"""
AG2 Checkpoint System

A comprehensive checkpoint system for AG2 (AutoGen 2) multi-agent conversations
that enables saving agent states at each conversation step and allows reloading
and resuming from any checkpoint.
"""

__version__ = "0.1.0"

# Core components
from .core import CheckpointManager, CheckpointData, create_checkpoint_manager
from .exceptions import (
    CheckpointError,
    SerializationError, 
    RestorationError,
    CheckpointNotFoundError,
    InvalidCheckpointError,
    StateConsistencyError,
    VersionCompatibilityError
)
from .utils import (
    generate_checkpoint_id,
    calculate_state_hash,
    format_checkpoint_summary,
    get_ag2_version
)

# Wrapper components
try:
    from .wrappers import (
        CheckpointableGroupChat,
        CheckpointingGroupChatManager,
        create_checkpointing_manager
    )
    _WRAPPERS_AVAILABLE = True
except ImportError:
    _WRAPPERS_AVAILABLE = False
    CheckpointableGroupChat = None
    CheckpointingGroupChatManager = None
    create_checkpointing_manager = None

# Restoration components
try:
    from .restoration import (
        CheckpointValidator,
        CheckpointLoader,
        AgentRecreator,
        ConversationContinuator,
        CheckpointRestorer
    )
    _RESTORATION_AVAILABLE = True
except ImportError:
    _RESTORATION_AVAILABLE = False
    CheckpointValidator = None
    CheckpointLoader = None
    AgentRecreator = None
    ConversationContinuator = None
    CheckpointRestorer = None

__all__ = [
    "CheckpointManager",
    "CheckpointData",
    "create_checkpoint_manager",
    "CheckpointError",
    "SerializationError",
    "RestorationError", 
    "CheckpointNotFoundError",
    "InvalidCheckpointError",
    "StateConsistencyError",
    "VersionCompatibilityError",
    "generate_checkpoint_id",
    "calculate_state_hash",
    "format_checkpoint_summary",
    "get_ag2_version",
]

# Add wrappers to __all__ if available
if _WRAPPERS_AVAILABLE:
    __all__.extend([
        "CheckpointableGroupChat",
        "CheckpointingGroupChatManager", 
        "create_checkpointing_manager"
    ])

# Add restoration components to __all__ if available
if _RESTORATION_AVAILABLE:
    __all__.extend([
        "CheckpointValidator",
        "CheckpointLoader",
        "AgentRecreator",
        "ConversationContinuator",
        "CheckpointRestorer"
    ])