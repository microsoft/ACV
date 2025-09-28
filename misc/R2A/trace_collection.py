from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer
import torch
from datasets import load_dataset
import json
import os
import argparse
from typing import Dict, List, Optional

# Model name mapping for selected cases
MODEL_NAME_MAPPING = {
    "DeepSeek-R1-Distill-Llama-8B": "llama-8B",
    "DeepSeek-R1-Distill-Qwen-7B": "qwen-7B",
    "DeepSeek-R1-Distill-Qwen-1.5B": "qwen-1p5B",
}

# Datasets
DATASET_CONFIG = {
    "MATH-500":
        {
            "path": "HuggingFaceH4/MATH-500",
            "subset": None,
            "split": "test",
            "unique_id_key": "unique_id",
        },
    "WildBench":
        {
            "path": "allenai/WildBench",
            "subset": "v2",
            "split": "test",
            "unique_id_key": "session_id",
        },
}

# Constants
DEFAULT_OUTPUT_DIR = "output/reasoning_traces"
WITHOUT_R_MODES = ["default", "empty", "finished"]

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run inference on a math dataset with a language model")
    
    parser.add_argument("--model_path", type=str, default="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                        help="Path or name of the model to use")
    parser.add_argument("--dataset", type=str, default="MATH-500", choices=list(DATASET_CONFIG.keys()),
                        help="Name of the dataset to use, options: " + ", ".join(DATASET_CONFIG.keys()))
    parser.add_argument("--max_new_tokens", type=int, default=10000,
                        help="Maximum number of new tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.6,
                        help="Temperature for sampling")
    parser.add_argument("--with_reasoning", action="store_true", default=False,
                        help="Whether to include reasoning in the prompt")
    parser.add_argument("--with_math_instruction", action="store_true", default=False,
                        help="Whether to include math instruction in the prompt")
    parser.add_argument("--save_frequency", type=int, default=1,
                        help="Frequency to save results")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of samples to process (default: process all)")
    parser.add_argument("--withoutR_mode", type=str, default="default",
                        choices=WITHOUT_R_MODES,
                        help="Mode for withoutR: default, empty, or finished thinking")
    parser.add_argument("--selected_cases_file_path", type=str, default=None,
                        help="Path to a file containing selected cases (optional)")
    parser.add_argument("--run_index", type=int, default=0,
                        help="Index of the run for logging purposes")
    parser.add_argument("--greedy_decoding", action="store_true", default=False,
                        help="Use greedy decoding instead of sampling during generation")
    
    return parser.parse_args()

def get_run_name(args, model_name: str) -> str:
    """Generate a unique run name based on configuration."""
    run_name = model_name
    
    # Add reasoning indicator
    if args.with_reasoning:
        run_name += "_withR"
    else:
        run_name += "_withoutR"
        
    # Add mode for non-reasoning runs
    if not args.with_reasoning:
        if args.withoutR_mode == "empty":
            run_name += "_empty"
        elif args.withoutR_mode == "finished":
            run_name += "_finished"
            
    # Add decoding strategy
    run_name += "_greedy" if args.greedy_decoding else "_sampling"
    
    # Add selected cases indicator if applicable
    if args.selected_cases_file_path:
        run_name += "_selected_cases_run"
        
    return run_name

def load_existing_results(output_path: str) -> Dict[str, dict]:
    """Load existing results from the output file if it exists."""
    existing_results = {}
    try:
        with open(output_path, 'r') as f:
            for line in f:
                res = json.loads(line)
                existing_results[res['unique_id']] = res
        print(f"Loaded {len(existing_results)} existing results from {output_path}")
    except FileNotFoundError:
        print(f"No existing results found. Creating new output file at {output_path}")
    return existing_results

def load_selected_cases(args, model_name: str) -> List[str]:
    """Load selected cases from a file if provided."""
    if not args.selected_cases_file_path:
        return []
        
    with open(args.selected_cases_file_path, 'r') as f:
        selected_cases_dict = json.load(f)
        
    # Determine the key for looking up selected cases
    if args.with_reasoning:
        model_key = MODEL_NAME_MAPPING[model_name] + "-withR"
    else:
        model_key = MODEL_NAME_MAPPING[model_name] + "-withoutR"
        
    selected_cases = selected_cases_dict.get(model_key, [])
    print(f"Selected cases loaded: {len(selected_cases)} cases for model {model_key}")
    
    if not selected_cases:
        raise ValueError("Selected cases list is empty or not found in the file.")
        
    return selected_cases

def get_raw_problem(sample: dict, dataset_name: str) -> str:
    """Extract the raw problem from the sample based on the dataset."""
    if dataset_name == "MATH-500":
        return sample['problem']
    elif dataset_name == "WildBench":
        return sample['conversation_input'][0]['content']
    else:
        raise ValueError(f"Unsupported dataset: {dataset_name}")

def format_problem(problem: str, args) -> str:
    """Format the problem with appropriate instructions and reasoning tags."""
    # Add instruction if needed
    instruction = r" Please reason step by step, and put your final answer within \boxed{}." \
                  if args.with_math_instruction else ""
    
    # Handle reasoning format based on arguments
    if args.with_reasoning:
        return problem + instruction + ' <think>\n'
    else:
        # Different modes for without reasoning
        if args.withoutR_mode == "empty":
            return problem + instruction + ' <think>\n\n</think>'
        elif args.withoutR_mode == "finished":
            return problem + instruction + ' <think>\nOkay, I think I have finished thinking.\n</think>'
        else:  # Default mode
            return problem + instruction + ' <think>\n\n</think>'

def save_results(results: List[dict], output_path: str) -> None:
    """Save results to the output file."""
    with open(output_path, 'a') as f:
        for res in results:
            json.dump(res, f)
            f.write('\n')
    print(f"Saved {len(results)} results to {output_path}")

def main():
    args = parse_arguments()
    
    # Disable gradient computation for inference
    torch.set_grad_enabled(False)
    
    # Extract model and dataset names
    model_name = args.model_path.split('/')[-1]
    dataset_name = args.dataset
    
    # Generate run name and output path
    run_name = get_run_name(args, model_name)
    args.output_path = f"{DEFAULT_OUTPUT_DIR}/{dataset_name}_{run_name}_{args.run_index}.jsonl"
    print(f"Output path set to: {args.output_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    
    # Load tokenizer and model
    print(f"Loading model: {args.model_path}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path, 
        torch_dtype=torch.bfloat16, 
        device_map="auto", 
        trust_remote_code=True
    )
    model.eval()
    
    # Load dataset
    print(f"Loading dataset: {DATASET_CONFIG[dataset_name]['path']}")
    if DATASET_CONFIG[dataset_name]['subset'] is not None:
        dataset = load_dataset(DATASET_CONFIG[dataset_name]['path'], DATASET_CONFIG[dataset_name]['subset'], split=DATASET_CONFIG[dataset_name]['split'])
    else:
        dataset = load_dataset(DATASET_CONFIG[dataset_name]['path'], split=DATASET_CONFIG[dataset_name]['split'])
    
    # Load existing results
    existing_results = load_existing_results(args.output_path)
    
    # Load selected cases if provided
    selected_cases = load_selected_cases(args, model_name) if args.selected_cases_file_path else []
    
    # Process samples
    results_buffer = []
    for i, sample in enumerate(dataset):
        if args.limit is not None and i >= args.limit:
            break
            
        sample_id = sample[DATASET_CONFIG[dataset_name]['unique_id_key']]

        # Skip if not in selected cases (when using selected cases)
        if len(selected_cases) > 0 and sample_id not in selected_cases:
            print(f"Skipping sample {i} (unique_id: {sample_id}) - not in selected cases.")
            continue
    
        # Skip samples that already have results
        if sample_id in existing_results:
            print(f"Skipping sample {i} (unique_id: {sample_id}) - already processed.")
            continue
    
        # Print sample information
        raw_problem = get_raw_problem(sample, dataset_name)
        print(f"Processing sample {i}: {raw_problem}")
    
        # Format the problem
        problem = format_problem(raw_problem, args)
        inputs = tokenizer(problem, return_tensors="pt").to(model.device)
    
        # Configure streamer for output
        streamer = TextStreamer(tokenizer, skip_special_tokens=False)
        
        # Generate response
        outputs = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=not args.greedy_decoding,
            temperature=args.temperature if not args.greedy_decoding else None,
            streamer=streamer
        )
    
        # Decode the response
        response = tokenizer.decode(outputs[0], skip_special_tokens=False)
    
        # Store result
        results_buffer.append({
            'unique_id': sample_id,
            'problem': raw_problem,
            'response': response,
        })
    
        # Save results periodically
        if (i + 1) % args.save_frequency == 0:
            save_results(results_buffer, args.output_path)
            results_buffer = []  # Clear the buffer after saving
    
    # Save any remaining results
    if results_buffer:
        save_results(results_buffer, args.output_path)

if __name__ == "__main__":
    main()
