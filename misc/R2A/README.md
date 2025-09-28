# From Reasoning to Answer: Empirical, Attention-Based and Mechanistic Insights into Distilled DeepSeek R1 Models

Code for the above paper that is accepted by EMNLP 2025 Main Conference.

## Setup the environment

```bash
conda create -n r2a python=3.11
conda activate r2a
pip install -r requirements.txt
cd TransformerLens
pip install -e .
```

## 0. Collect the Reasoning Traces
Note1: currently, we use the generation function from `transformer` package, which is not optimized for speed.
Note2：Not use `--with_math_instruction` for the `WildBench` dataset, as it is not a primarily math dataset.

1. With reasoning:
```python
python trace_collection.py \
    --model_path "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B" \
    --dataset "MATH-500" \
    --with_math_instruction \
    --with_reasoning \
    --limit 1  # Uncomment for testing with a single example 
```

```python
python trace_collection.py \
    --model_path "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B" \
    --dataset "WildBench" \
    --with_reasoning \
    --limit 1  # Uncomment for testing with a single example 
```

2. Without reasoning:
```python
python trace_collection.py \
    --model_path "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B" \
    --dataset "MATH-500" \
    --with_math_instruction \
    --withoutR_mode "finished" \
    --limit 1  # Uncomment for testing with a single example
```

```python
python trace_collection.py \
    --model_path "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B" \
    --dataset "WildBench" \
    --withoutR_mode "finished" \
    --limit 1  # Uncomment for testing with a single example
```

Currently, we have provided the traces for `MATH-500` and `WildBench` datasets in the `output/reasoning_traces` folder.

## 1. Empirical Evaluation (i.e., Section 3 of the Paper)

Refer to the notebook `1_empirical_evaluation.ipynb` for details.

## 2. Attention Analysis (i.e., Section 4 of the Paper)

Refer to the notebook `2_attn_analysis_overall.ipynb` for the overall segment-level attention analysis.

Refer to the notebook `2_attn_analysis_RFHs.ipynb` for the study on Reasoning-Focused Heads (RFHs).

## 3. Mechanistic Intervention (i.e., Section 5 of the Paper)

Refer to the notebook `3_mechanistic_intervention.ipynb` for details.