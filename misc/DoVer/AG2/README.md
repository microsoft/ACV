# AG2 Checkpoint System

This folder now keeps a single README as the canonical description of the AutoGen (AG2) checkpoint system. It summarizes the purpose, layout, workflows, and related documentation so you can quickly confirm the material is concrete.

## Purpose and Capabilities

- **Conversation persistence**: Serialize every agent message, LLM configuration, tool state, and custom metadata.
- **Restoration and continuation**: Resume from any checkpoint and continue for additional rounds, enabling forks and what-if experiments.
- **Termination signal capture**: Record tokens such as `SOLUTION_FOUND` or custom stop phrases for downstream automation.
- **Code execution awareness**: Preserve `code_execution_config`, tool outputs, and failure traces.
- **Auditable logs**: Store artifacts under `logs/session_YYYYMMDD_HHMMSS/`, including checkpoints, chat history, problem statements, and metadata.

## Directory Map

```
AG2/
|-- checkpoint_system/                  # Core package, installable via pip -e
|   |-- core.py                         # CheckpointManager and data models
|   |-- wrappers.py                     # CheckpointingGroupChatManager wrapper
|   |-- restoration.py                  # CheckpointRestorer logic
|   |-- exceptions.py                   # Custom exceptions
|   `-- README.md                       # Detailed API reference
|-- mathchat_with_checkpoints.py        # Example: generate checkpoints
|-- test_checkpoint_continuation.py     # Example: continue from a checkpoint
|-- CHECKPOINT_SYSTEM_DOCUMENTATION.md  # Design, serialization format, troubleshooting
|-- EXPERIMENT_DOCUMENTATION.md         # Real experiment records
`-- logs/                               # Runtime artifacts (safe to clean up)
```

## Environment and Dependencies

1. Python 3.11 (same as the root project). Recommended workflow:
   ```bash
   conda create -n ada python=3.11 -y
   conda activate ada
   ```
2. From the repo root install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e src/autogen-ext
   pip install -e src/autogen-agentchat
   pip install -e src/agdebugger
   ```
3. Export usable OpenAI or Azure OpenAI credentials:
   ```bash
   set OPENAI_API_KEY=...
   set AZURE_OPENAI_API_KEY=...
   ```

## Common Workflow

### 1. Generate checkpoints

```bash
cd AG2
python mathchat_with_checkpoints.py --rounds 8 --session-name demo_session
```

- Default prompt is a math conversation; override via `--problem-file path/to/task.txt`.
- Outputs land in `logs/session_<timestamp>/checkpoints/` plus `checkpoints_metadata.json`.

### 2. Continue from a checkpoint

```bash
python test_checkpoint_continuation.py ^
    logs/session_20251116_130229/checkpoints/checkpoint_3_message_appended_20251116_130239.json ^
    --rounds 5 --output-root logs/session_20251116_130229/continuations
```

- Restores agents, `llm_config`, registered tools, and chat history.
- Continuations are written to `continuation_<timestamp>/` for side-by-side comparison.

### 3. Inspect generated artifacts

- `chat_history.json`: full ordered message list with roles.
- `problem_statement.txt`: original task description.
- `session_metadata.json`: snapshot of model, tool, and runtime settings.
- `checkpoints_metadata.json`: summary of all checkpoint triggers and timestamps.

## Testing and Verification

```bash
# Produce a fresh sample
python mathchat_with_checkpoints.py --rounds 3

# Run continuation smoke tests for every checkpoint
for /f "delims=" %f in ('dir /b /s logs\\session_*\\checkpoints\\checkpoint_*.json') do (
    python test_checkpoint_continuation.py %f --rounds 2
)
```

Recommended validation focus:
- Termination detection: verify custom stop tokens in `checkpoints_metadata.json`.
- Interrupted runs: stop `mathchat_with_checkpoints.py` mid-flight, then recover via `test_checkpoint_continuation.py`.
- Code execution parity: ensure tool execution logs persist after continuation.

## Related Documentation

- `CHECKPOINT_SYSTEM_DOCUMENTATION.md`: deep-dive into design decisions, data formats, and troubleshooting.
- `EXPERIMENT_DOCUMENTATION.md`: empirical setups, metrics, and lessons learned.
- `checkpoint_system/README.md`: API-level documentation for the package itself.

Update this README whenever new capabilities land so the AG2 directory always has a single, authoritative description.
