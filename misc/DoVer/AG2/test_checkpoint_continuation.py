"""
Test script for checkpoint continuation - restore and continue conversation from message_appended checkpoints ONLY.

This script ONLY supports integer checkpoint continuation from message_appended checkpoints 
(e.g., checkpoint_2_message_appended_*.json). Half-integer checkpoints (speaker_reply_generated) 
are NOT supported and will raise an error.

Usage:
    python test_checkpoint_continuation.py <message_appended_checkpoint.json>
    python test_checkpoint_continuation.py logs/session_20251115_143313/checkpoints/checkpoint_2_message_appended_20251115_143318.json

Supported checkpoint types:
    - message_appended (integer steps): ✅ Supported
    - speaker_reply_generated (half-integer steps): ❌ NOT supported

Note: Only message_appended checkpoints are supported for continuation.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add checkpoint system to path
checkpoint_system_path = Path(__file__).parent
if str(checkpoint_system_path) not in sys.path:
    sys.path.insert(0, str(checkpoint_system_path))

# Add AG2 path
ag2_path = Path(__file__).parent / "ag2-0.10.0"
if str(ag2_path) not in sys.path:
    sys.path.insert(0, str(ag2_path))

# Import checkpoint system components
from checkpoint_system import CheckpointRestorer
from checkpoint_system.exceptions import InvalidCheckpointError, RestorationError, CheckpointError

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_ROUNDS = 20


def continue_conversation_from_checkpoint(checkpoint_file: Path, max_rounds: int = DEFAULT_MAX_ROUNDS) -> bool:
    """
    Continue conversation from checkpoint using the checkpoint system.
    
    Args:
        checkpoint_file: Path to checkpoint file
        max_rounds: Maximum additional conversation rounds
        
    Returns:
        True if continuation was successful, False otherwise
    """
    try:
        # Create restorer instance
        restorer = CheckpointRestorer.create_restorer()
        
        # Continue the conversation
        return restorer.continue_conversation(checkpoint_file, max_rounds)
        
    except (InvalidCheckpointError, RestorationError, CheckpointError) as e:
        logger.error(f"Checkpoint continuation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during continuation: {e}")
        return False


def main() -> int:
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Continue conversation from a message_appended checkpoint (integer steps only)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_checkpoint_continuation.py logs/session_20251115_143313/checkpoints/checkpoint_2_message_appended_20251115_143318.json
  python test_checkpoint_continuation.py checkpoint_2_message_appended_*.json --rounds 3

Supported checkpoint types:
  ✅ message_appended (integer steps) - e.g., checkpoint_2_message_appended_*.json
  ❌ speaker_reply_generated (half-integer steps) - NOT supported, will raise error

Note: Only message_appended checkpoints are supported for continuation.
"""
    )
    
    parser.add_argument('checkpoint_file', type=str,
                       help='Path to the checkpoint JSON file (MUST be message_appended type)')
    
    parser.add_argument('--rounds', '-r', type=int, default=DEFAULT_MAX_ROUNDS,
                       help=f'Maximum additional conversation rounds (default: {DEFAULT_MAX_ROUNDS})')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate checkpoint file exists
    checkpoint_file = Path(args.checkpoint_file)
    if not checkpoint_file.exists():
        logger.error(f"Checkpoint file not found: {checkpoint_file}")
        return 1
    
    if checkpoint_file.suffix != '.json':
        logger.error(f"Checkpoint file must be a JSON file: {checkpoint_file}")
        return 1
    
    # Run continuation
    try:
        success = continue_conversation_from_checkpoint(checkpoint_file, args.rounds)
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
