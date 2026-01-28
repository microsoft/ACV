"""
Custom exceptions for the AG2 checkpoint system.
"""


class CheckpointError(Exception):
    """Base exception for checkpoint system errors."""
    pass


class SerializationError(CheckpointError):
    """Raised when state serialization fails."""
    pass


class RestorationError(CheckpointError):
    """Raised when state restoration fails."""
    pass


class CheckpointNotFoundError(CheckpointError):
    """Raised when a requested checkpoint is not found."""
    pass


class InvalidCheckpointError(CheckpointError):
    """Raised when a checkpoint is corrupted or invalid."""
    pass


class StateConsistencyError(CheckpointError):
    """Raised when there are state consistency issues."""
    pass


class VersionCompatibilityError(CheckpointError):
    """Raised when checkpoint was created with incompatible AG2 version."""
    pass