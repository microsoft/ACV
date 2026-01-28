"""
Enhanced MathChat with Checkpointing System

This module combines the original mathchat.py functionality with the checkpoint system,
creating a complete session with all standard mathchat.py logs plus checkpoint capabilities.

Session structure will be:
logs/session_YYYYMMDD_HHMMSS/
├── ag2_runtime.db              # AG2 runtime logging
├── chat_history.json           # Complete chat history  
├── console.log                 # Console output
├── final_summary.txt           # Final summary
├── problem_statement.txt       # Original problem
├── session_metadata.json       # Session metadata
└── checkpoints/                # Checkpoint system directory
    ├── checkpoints_metadata.json
    ├── cache.db                # Checkpoint storage
    └── checkpoint_*.json       # Individual checkpoints
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from autogen import ConversableAgent, LLMConfig
from autogen.agentchat.groupchat import GroupChat, GroupChatManager
import autogen.runtime_logging

# Import checkpoint system
from checkpoint_system.core import create_checkpoint_manager
from checkpoint_system.wrappers import CheckpointingGroupChatManager


# ============================================================
# 1. Setup Session-Based Logging (from mathchat.py)
# ============================================================
def create_session_directory(base_log_dir: str = "logs"):
    """Create a unique session directory for this run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"session_{timestamp}"
    
    base_path = Path(base_log_dir)
    base_path.mkdir(exist_ok=True)
    
    session_dir = base_path / session_id
    session_dir.mkdir(exist_ok=True)
    
    return session_dir, session_id, timestamp

def setup_logging(session_dir: Path):
    """Setup both console and file logging within the session directory."""
    
    # Setup console logging to file
    console_log_file = session_dir / "console.log"
    
    # Configure logging to both console and file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(console_log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Session started. All logs will be saved to: {session_dir}")
    logger.info(f"Console logs: {console_log_file}")
    
    return logger, console_log_file

# Create session directory and setup logging
session_dir, session_id, session_timestamp = create_session_directory()
logger, console_log_file = setup_logging(session_dir)


# ============================================================
# 2. Load LLM configuration (from mathchat.py)
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be set before running mathchat_with_checkpoints.")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

llm_config = LLMConfig(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    base_url=OPENAI_BASE_URL,
    api_type="openai",
    api_key=OPENAI_API_KEY,
    max_tokens=4096,
)


# ============================================================
# 3. Load Prompts (from mathchat.py)
# ============================================================

from prompt import PROBLEM_SOLVER_SYSTEM_PROMPT, CODE_EXECUTOR_SYSTEM_PROMPT, VERIFIER_SYSTEM_PROMPT, STRUCTURED_MATHCHAT_IMPROVED_PROMPT

# ============================================================
# 4. Build agents + enhanced checkpointing GroupChat orchestration
# ============================================================

def build_enhanced_groupchat_with_checkpoints(llm_cfg: LLMConfig, max_rounds: int = 12, session_dir: Path = None, problem_context: str = ""):
    """Build GroupChat + CheckpointingGroupChatManager with full logging."""
    
    problem_solver = ConversableAgent(
        name="Agent_Problem_Solver",
        system_message=PROBLEM_SOLVER_SYSTEM_PROMPT,
        llm_config=llm_cfg,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        description="I am Agent Problem Solver, and I work collaboratively with other agents to tackle various challenges.",
    )

    code_executor = ConversableAgent(
        name="Agent_Code_Executor", 
        system_message=CODE_EXECUTOR_SYSTEM_PROMPT,
        llm_config=llm_cfg,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        code_execution_config={
            "work_dir": "mathchat_workspace",
            "use_docker": False,
        },
        description="I am Agent Code Executor, specializing in solving problems by writing Python code. I have the ability to execute Python code, so feel free to reach out whenever you need assistance with Python programming.",
    )

    verifier = ConversableAgent(
        name="Agent_Verifier",
        system_message=VERIFIER_SYSTEM_PROMPT,
        llm_config=llm_cfg,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=5,
        is_termination_msg=lambda msg: "SOLUTION_FOUND" in (msg.get("content", "") or ""),
        description="I am Agent Verifier. Please call on me when both Agent Code Executor and Agent Problem Solver have submitted their solutions, so I can verify their proposals and provide a final synthesis.",
    )
    
    agents = [problem_solver, code_executor, verifier]
    
    # Create GroupChat with proper termination settings
    groupchat = GroupChat(
        agents=agents,
        messages=[],
        max_round=max_rounds,
        send_introductions=True,
        speaker_selection_method="auto"
    )
    
    # Create CheckpointManager for this session
    checkpoint_manager = create_checkpoint_manager(session_dir=session_dir)
    
    # Create CheckpointingGroupChatManager with integrated logging
    chat_manager = CheckpointingGroupChatManager(
        name="chat_manager",
        groupchat=groupchat,
        checkpoint_manager=checkpoint_manager,
        problem_context=problem_context,
        llm_config=llm_cfg,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=3,
        system_message="You are a chat manager facilitating a conversation between agents to solve math problems.",
        is_termination_msg=lambda msg: "SOLUTION_FOUND" in (msg.get("content", "") or ""),
    )
    
    return agents, groupchat, chat_manager, verifier, checkpoint_manager


# ============================================================
# 5. Enhanced Run function with comprehensive logging + checkpoints
# ============================================================

def save_chat_history_to_file(chat_result, session_dir: Path):
    """Save the detailed chat history to a JSON file in the session directory."""
    
    # Create comprehensive chat log
    chat_log = {
        "session_id": session_id,
        "timestamp": session_timestamp,
        "chat_id": getattr(chat_result, 'chat_id', None),
        "summary": chat_result.summary,
        "chat_history": chat_result.chat_history,
        "cost": getattr(chat_result, 'cost', {}),
        "human_input": getattr(chat_result, 'human_input', [])
    }
    
    # Save to JSON file in session directory
    chat_log_file = session_dir / "chat_history.json"
    with open(chat_log_file, 'w', encoding='utf-8') as f:
        json.dump(chat_log, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"Chat history saved to: {chat_log_file}")
    return chat_log_file


def load_problem_from_trace(json_path: str | Path) -> str:
    """Load the math problem statement from the MAST JSON trace."""
    data = json.loads(Path(json_path).read_text())
    problems = data.get("problem_statement") or []
    if not problems:
        raise ValueError("JSON does not contain a non-empty 'problem_statement' list.")
    return str(problems[0]).strip()


def run_enhanced_mathchat_with_checkpoints(json_path: str | Path | None, max_rounds: int = 20) -> None:
    """Run enhanced MathChat with full mathchat.py logging + checkpoints."""
    
    logger.info(f"=== Starting Enhanced MathChat Session with Checkpoints: {session_id} ===")
    
    # Setup AG2 runtime logging in session directory (like mathchat.py)
    ag2_log_file = session_dir / "ag2_runtime.db"
    try:
        ag2_session_id = autogen.runtime_logging.start(
            logger_type="sqlite",
            config={"dbname": str(ag2_log_file)}
        )
        logger.info(f"AG2 runtime logging started. Session ID: {ag2_session_id}")
        logger.info(f"AG2 logs will be saved to: {ag2_log_file}")
    except Exception as e:
        logger.warning(f"Failed to start AG2 runtime logging: {e}")
        ag2_session_id = None

    try:
        if json_path is not None:
            problem_text = load_problem_from_trace(json_path)
        else:
            problem_text = "Gerald works at a daycare that pays him $30 every day. He worked for an entire week and spent a total of $100. How much does he have left?"
        
        # Save the problem statement to session directory (like mathchat.py)
        problem_file = session_dir / "problem_statement.txt"
        with open(problem_file, 'w', encoding='utf-8') as f:
            f.write(problem_text)
        
        logger.info("Problem statement: %s", problem_text)
        logger.info(f"Problem saved to: {problem_file}")

        # Use enhanced GroupChat approach with checkpoints
        agents, groupchat, chat_manager, verifier, checkpoint_manager = build_enhanced_groupchat_with_checkpoints(
            llm_config, max_rounds, session_dir, problem_text
        )
        
        logger.info("Using enhanced GroupChat with checkpoints...")
        logger.info(f"GroupChat configured with max_round={max_rounds}")
        logger.info(f"Checkpoints will be saved to: {checkpoint_manager.checkpoints_dir}")
        
        # Have the verifier initiate with the problem statement to match original trace
        chat_result = verifier.initiate_chat(
            chat_manager,
            message=problem_text,
            max_turns=max_rounds
        )
        
        # Extract results
        chat_history = chat_result.chat_history
        summary = chat_result.summary or "No summary available"
        
        logger.info(f"Enhanced GroupChat with checkpoints completed with {len(chat_history)} messages")
        
        # Save chat history to session directory (like mathchat.py)
        chat_log_file = save_chat_history_to_file(chat_result, session_dir)
        
        # Save checkpoint metadata
        checkpoints_metadata_file = checkpoint_manager.save_checkpoints_metadata()
        logger.info(f"Checkpoints metadata saved to: {checkpoints_metadata_file}")
        
        # Get checkpoint summary for session metadata
        checkpoint_summary = checkpoint_manager.get_checkpoints_summary()
        
        # Save execution metadata (enhanced version of mathchat.py)
        metadata_file = session_dir / "session_metadata.json"
        metadata = {
            "session_id": session_id,
            "timestamp": session_timestamp,
            "problem_text": problem_text,
            "max_rounds": max_rounds,
            "ag2_session_id": ag2_session_id,
            "approach_used": "enhanced_groupchat_with_checkpoints",
            "files": {
                "console_log": str(console_log_file.relative_to(session_dir)),
                "chat_history": str(chat_log_file.relative_to(session_dir)),
                "problem_statement": str(problem_file.relative_to(session_dir)),
                "ag2_runtime": str(ag2_log_file.relative_to(session_dir)) if ag2_session_id else None,
                "checkpoints_metadata": str(checkpoints_metadata_file.relative_to(session_dir))
            },
            "checkpoints": checkpoint_summary
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Session metadata saved to: {metadata_file}")
        
        # Save final results to a separate summary file in session directory (like mathchat.py)
        summary_file = session_dir / "final_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=== ENHANCED MATHCHAT EXECUTION SUMMARY ===\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Timestamp: {session_timestamp}\n")
            f.write(f"Approach: Enhanced GroupChat with Checkpoints\n")
            f.write(f"Problem: {problem_text}\n")
            f.write(f"Max Rounds: {max_rounds}\n")
            f.write(f"Session Directory: {session_dir}\n\n")
            
            f.write(f"Checkpoint Statistics:\n")
            f.write(f"  Total Checkpoints: {checkpoint_summary.get('checkpoint_count', 0)}\n")
            f.write(f"  Last Checkpoint: {checkpoint_summary.get('last_checkpoint_time', 'none')}\n")
            f.write(f"  Checkpoints Directory: {checkpoint_summary.get('checkpoints_directory', 'none')}\n\n")
            
            f.write(f"Final Summary: {summary}\n")
            f.write(f"\n=== FINAL SUMMARY (group manager) ===\n")
            f.write(f"{summary}\n")
        
        logger.info(f"Final summary saved to: {summary_file}")

        print("\n=== FINAL SUMMARY (group manager) ===\n")
        print(summary)
        
        print(f"\n=== SESSION COMPLETE ===")
        print(f"Session ID: {session_id}")
        print(f"Approach Used: Enhanced GroupChat with Checkpoints")
        print(f"All session files saved to: {session_dir}")
        print(f"  - Console Log: {console_log_file.name}")
        print(f"  - Chat History: {chat_log_file.name}")
        print(f"  - Problem Statement: {problem_file.name}")
        print(f"  - Final Summary: {summary_file.name}")
        print(f"  - Session Metadata: {metadata_file.name}")
        print(f"  - Checkpoints Directory: {checkpoint_manager.checkpoints_dir.name}/")
        print(f"  - Checkpoints Metadata: {checkpoints_metadata_file.name}")
        print(f"  - Total Checkpoints Created: {checkpoint_summary.get('checkpoint_count', 0)}")
        if ag2_session_id:
            print(f"  - AG2 Runtime Log: {ag2_log_file.name}")
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        # Save error log to session directory
        error_file = session_dir / "error_log.txt"
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(f"Error occurred at: {datetime.now()}\n")
            f.write(f"Error: {str(e)}\n")
            import traceback
            f.write(f"Traceback:\n{traceback.format_exc()}")
        
        logger.info(f"Error details saved to: {error_file}")
        raise
    finally:
        # Stop AG2 runtime logging
        if ag2_session_id:
            try:
                autogen.runtime_logging.stop()
                logger.info("AG2 runtime logging stopped")
            except Exception as e:
                logger.warning(f"Error stopping AG2 runtime logging: {e}")
        
        logger.info(f"=== Enhanced Session {session_id} Complete ===")
        print(f"\nSession directory: {session_dir}")

# ============================================================
# 8. Entry point
# ============================================================

if __name__ == "__main__":
    # Path to the JSON file containing the trace.
    # Change this if your file has a different name or location.
    # JSON_TRACE_PATH = "018efed1-9951-5512-a991-d2115e718547.json"
    JSON_TRACE_PATH = None  # Use None to run the default problem.

    run_enhanced_mathchat_with_checkpoints(JSON_TRACE_PATH)
