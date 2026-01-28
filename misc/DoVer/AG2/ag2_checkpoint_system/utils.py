"""
Utility functions for the AG2 checkpoint system.
"""

import json
import hashlib
import uuid
import os
from datetime import datetime
from typing import Any, Dict, Union, Optional
from pathlib import Path


def generate_checkpoint_id(prefix: str = "checkpoint") -> str:
    """Generate a unique checkpoint ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{unique_suffix}"


def calculate_state_hash(state_data: Dict[str, Any]) -> str:
    """Calculate a hash of the state data for integrity checking."""
    # Create a stable string representation for hashing
    state_json = json.dumps(state_data, sort_keys=True, default=str)
    return hashlib.sha256(state_json.encode()).hexdigest()


def safe_json_serialize(obj: Any, _seen: Optional[set] = None) -> Any:
    """
    Safely serialize an object to JSON-compatible format.
    Enhanced to handle lambda functions and prevent infinite recursion.
    """
    if _seen is None:
        _seen = set()
    
    # Check for circular references
    obj_id = id(obj)
    if obj_id in _seen:
        return f"<circular reference: {type(obj).__name__}>"
    
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        _seen.add(obj_id)
        try:
            result = [safe_json_serialize(item, _seen) for item in obj]
            return result
        finally:
            _seen.discard(obj_id)
    elif isinstance(obj, dict):
        _seen.add(obj_id)
        try:
            result = {}
            for k, v in obj.items():
                try:
                    result[str(k)] = safe_json_serialize(v, _seen)
                except Exception:
                    # Skip non-serializable keys/values
                    result[str(k)] = f"<non-serializable: {type(v).__name__}>"
            return result
        finally:
            _seen.discard(obj_id)
    elif callable(obj):
        # Enhanced handling for functions/callables including lambdas
        name = getattr(obj, '__name__', '<lambda>')
        if name == '<lambda>':
            return {
                '__type__': 'lambda',
                '__module__': getattr(obj, '__module__', 'unknown'),
                '__qualname__': getattr(obj, '__qualname__', 'unknown'),
                '__str__': '<lambda function>'
            }
        else:
            return {
                '__type__': 'function',
                '__name__': name,
                '__module__': getattr(obj, '__module__', 'unknown'),
                '__qualname__': getattr(obj, '__qualname__', 'unknown'),
            }
    elif hasattr(obj, '__dict__'):
        # For objects with __dict__, serialize their attributes safely
        _seen.add(obj_id)
        try:
            safe_dict = {}
            for attr_name, attr_value in obj.__dict__.items():
                try:
                    safe_dict[attr_name] = safe_json_serialize(attr_value, _seen)
                except Exception:
                    # Skip problematic attributes
                    safe_dict[attr_name] = f"<non-serializable: {type(attr_value).__name__}>"
            
            return {
                '__type__': obj.__class__.__name__,
                '__module__': obj.__class__.__module__,
                '__data__': safe_dict
            }
        finally:
            _seen.discard(obj_id)
    else:
        # For other types, convert to string representation
        try:
            return {
                '__type__': type(obj).__name__,
                '__str__': str(obj)
            }
        except Exception:
            return {
                '__type__': type(obj).__name__,
                '__str__': '<unrepresentable object>'
            }


def create_session_checkpoint_directory(session_dir: Union[str, Path]) -> Path:
    """Create a checkpoint directory within an existing session directory."""
    session_path = Path(session_dir)
    
    # Create checkpoint subdirectory
    checkpoint_dir = session_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Create metadata subdirectory
    metadata_dir = checkpoint_dir / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    
    return checkpoint_dir


def validate_checkpoint_data(checkpoint_data: Dict[str, Any]) -> bool:
    """Validate that checkpoint data has required fields."""
    required_fields = [
        'checkpoint_id',
        'timestamp', 
        'current_round',
        'total_steps',
        'groupchat_state',
        'manager_state',
        'agent_states',
        'session_metadata'
    ]
    
    for field in required_fields:
        if field not in checkpoint_data:
            return False
    
    return True


def get_ag2_version() -> str:
    """Get the current AG2 version for compatibility checking."""
    try:
        # Try to import AG2 version
        from autogen.version import __version__
        return __version__
    except ImportError:
        # Fallback if version module not available
        return "unknown"


def format_checkpoint_summary(checkpoint_data: Dict[str, Any]) -> str:
    """Format a human-readable summary of checkpoint data."""
    return f"""
Checkpoint Summary:
  ID: {checkpoint_data.get('checkpoint_id', 'unknown')}
  Timestamp: {checkpoint_data.get('timestamp', 'unknown')}
  Round: {checkpoint_data.get('current_round', 'unknown')} / {checkpoint_data.get('groupchat_state', {}).get('max_round', 'unknown')}
  Total Steps: {checkpoint_data.get('total_steps', 'unknown')}
  Agents: {len(checkpoint_data.get('agent_states', {}))}
  AG2 Version: {checkpoint_data.get('session_metadata', {}).get('ag2_version', 'unknown')}
    """.strip()


def ensure_directory_exists(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj