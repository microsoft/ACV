# Dover M1 Agent Debugging Toolkit

Tools to replay, debug, and iterate on Magentic-One multi-agent runs. Built on AutoGen AgentChat + AGDebugger with helper scripts for running, analyzing, and intervening in sessions.

## Requirements
- Conda (Python 3.11)
- Node.js 18+ (for AGDebugger frontend)
- Git + C/C++ toolchain (for some AutoGen extensions)
- Optional: Playwright (`playwright install --with-deps chromium`)

## Environment setup (Dover)
```bash
# Create and enter the Dover environment
conda create -n dover python=3.11
conda activate dover

# Base Python dependencies
pip install -r requirements.txt

# Build AGDebugger frontend before installing the editable package
pushd src/agdebugger/frontend
npm install
npm run build
popd

# Install local packages in editable mode
pip install -e src/agdebugger
pip install -e src/autogen-agentchat
pip install -e src/autogen-ext
```


## Run baseline and evaluate
```bash
# Run scenario 1 and capture logs
python scripts/simulation_runner.py --scenario 1 --model gpt-4o --port 8081 --auto-exit

# Evaluate baseline
python scripts/evaluator_trial.py --scenario 1
```
If `correct: false`, proceed:
```bash
# Analyze + summarize trials (requires Azure OpenAI)
python scripts/log_decomposer.py --scenario 1 --model gpt-4o
python scripts/trial_summarizer.py --scenario 1 --model gpt-4o

# Recommend + apply interventions, then re-evaluate
python scripts/intervention_recommender_trial.py --scenario 1 --model gpt-4o
python scripts/intervener_trial.py --scenario 1 --model gpt-4o
python scripts/evaluator_trial.py --scenario 1
```

## Key scripts (at a glance)
- simulation_runner: run a full session and log everything
- log_decomposer / trial_summarizer: structure and summarize runs
- intervention_recommender_trial: generate structured interventions
- intervener_trial: apply interventions and replay via AGDebugger
- state_loader: restore history/cache into the UI

## Repo layout
```
Dover/
|-- README.md                         # Toolkit overview (this file)
|-- requirements.txt                  # Shared Python dependencies
|-- AG2/                              # AutoGen checkpoint system (see AG2/README.md)
|-- scripts/                          # Entry points for running and evaluating scenarios
|   |-- batch_milestone_evaluation.py
|   |-- const.py
|   |-- intervener_trial.py
|   |-- intervention_recommender.py
|   |-- intervention_recommender_trial.py
|   |-- log_decomposer.py
|   |-- m1_agdebugger_test.py
|   |-- simulation_runner.py
|   |-- state_loader.py
|   `-- trial_summarizer.py
|-- src/
|   |-- agdebugger/                   # FastAPI backend + Typer CLI + Vite frontend
|   |-- autogen-agentchat/            # Vendored AgentChat extensions
|   `-- autogen-ext/                  # Additional local libraries
|-- Agents_Failure_Attribution/       # Scenario specs and attribution data
|-- analysis/                         # Ad-hoc studies / generated analytics
|-- logs/                             # Scenario outputs (history, cache, eval, trials)
`-- .vscode/                          # Workspace settings
```

> For the dedicated AG2 checkpoint system documentation (structure, workflows, testing), open `Dover/AG2/README.md`.
