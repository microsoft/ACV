import os
import json
from jaxtyping import Float
import torch

def logits_to_ave_logit_diff(logits, answer_tokens, per_prompt=False):
    # Only the final logits are relevant for the answer
    final_logits = logits[:, -1, :]
    answer_logits = final_logits.gather(dim=-1, index=answer_tokens)
    answer_logit_diff = answer_logits[:, 0] - answer_logits[:, 1]
    if per_prompt:
        return answer_logit_diff
    else:
        return answer_logit_diff.mean()

def logits_to_metrics(logits, answer_tokens):
    # Only the final logits are relevant for the answer
    # Directly index batch dimension as 0
    assert logits.shape[0] == 1, "Batch size should be 1 for this function"
    final_logits = logits[0, -1, :]
    
    # Get logits for answer tokens
    answer_logits = final_logits.gather(dim=-1, index=answer_tokens[0])
    answer_logit_diff = answer_logits[0] - answer_logits[1]
    
    # Convert to log probabilities
    log_probs = torch.log_softmax(final_logits, dim=-1)
    answer_log_probs = log_probs.gather(dim=-1, index=answer_tokens[0])
    answer_log_prob_diff = answer_log_probs[0] - answer_log_probs[1]
    
    # Convert to probabilities
    probs = torch.softmax(final_logits, dim=-1)
    answer_probs = probs.gather(dim=-1, index=answer_tokens[0])
    answer_prob_diff = answer_probs[0] - answer_probs[1]
    
    # Get ranks
    ranks = torch.argsort(torch.argsort(final_logits, dim=-1, descending=True), dim=-1)
    answer_ranks = ranks.gather(dim=-1, index=answer_tokens[0])
    answer_rank_diff = answer_ranks[0] - answer_ranks[1]  # Lower rank is better
    
    return {
        'logits': answer_logits.detach().cpu().float().numpy().tolist(),
        'logit_diff': answer_logit_diff.item(),
        'log_probs': answer_log_probs.detach().cpu().float().numpy().tolist(),
        'log_prob_diff': answer_log_prob_diff.item(),
        'probs': answer_probs.detach().cpu().float().numpy().tolist(),
        'prob_diff': answer_prob_diff.item(),
        'ranks': answer_ranks.detach().cpu().float().numpy().tolist(),
        'rank_diff': answer_rank_diff.item()
    }

def normalize_patched_logit_diff(patched_logit_diff, clean_average_logit_diff, corrupted_average_logit_diff):
    # Subtract corrupted logit diff to measure the improvement, divide by the total improvement from clean to corrupted to normalise
    # 0 means zero change, negative means actively made worse, 1 means totally recovered clean performance, >1 means actively *improved* on clean performance
    return (patched_logit_diff - corrupted_average_logit_diff) / (
        clean_average_logit_diff - corrupted_average_logit_diff
    )

def get_corrupted_average_logit_diff(avg_logit_diff_fp, scenario_id, model, corrupted_tokens, answer_tokens, is_save=True):
    
    corrupted_average_logit_diff = None

    if not is_save:
        model_output = model(corrupted_tokens)
        # Check if model output is a tensor or an object with logits attribute
        corrupted_logits = model_output if isinstance(model_output, torch.Tensor) else model_output.logits
        corrupted_average_logit_diff = logits_to_ave_logit_diff(corrupted_logits, answer_tokens)
        return corrupted_average_logit_diff
    
    try:
        if os.path.exists(avg_logit_diff_fp):
            with open(avg_logit_diff_fp, "r") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get('scenario') == scenario_id:
                        corrupted_average_logit_diff = data.get('corrupted_average_logit_diff')
                        print(f"Loaded corrupted_average_logit_diff: {corrupted_average_logit_diff}")
                        break
    except Exception as e:
        print(f"Error loading from logit diff file: {e}")
        return None

    # If not found in file, compute it
    if corrupted_average_logit_diff is None:
        # Use a more lightweight approach: just get logits without caching
        model_output = model(corrupted_tokens)
        # Check if model output is a tensor or an object with logits attribute
        corrupted_logits = model_output if isinstance(model_output, torch.Tensor) else model_output.logits
        corrupted_average_logit_diff = logits_to_ave_logit_diff(corrupted_logits, answer_tokens)
        
        # Save results
        with open(avg_logit_diff_fp, "a") as f:
            json.dump({
                'scenario': scenario_id,
                'corrupted_average_logit_diff': float(corrupted_average_logit_diff.item())
            }, f)
            f.write('\n')  # Add newline for JSONL format
        print("Warning: Corrupted average logit diff not found in file, computed it instead. Need to check CUDA memory usage.")
        print(f"Saved corrupted average logit diff: {corrupted_average_logit_diff} to {avg_logit_diff_fp}")

    return corrupted_average_logit_diff

def save_patching_results(answer_patching_fp, scenario_id, result_data):

    # Initialize empty data or load existing data
    data_list = []
    if os.path.exists(answer_patching_fp) and os.path.getsize(answer_patching_fp) > 0:
        with open(answer_patching_fp, 'r') as f:
            for line in f:
                if line.strip():  # Skip empty lines
                    data_list.append(json.loads(line))

    # Check if the scenario_id already exists
    existing_entry_index = None
    for i, entry in enumerate(data_list):
        if entry.get('scenario_id') == scenario_id:
            existing_entry_index = i
            break

    # Update existing entry or append new one
    if existing_entry_index is not None:
        data_list[existing_entry_index] = result_data
    else:
        data_list.append(result_data)

    # Write back to file
    with open(answer_patching_fp, 'w') as f:
        for entry in data_list:
            f.write(json.dumps(entry) + '\n')

    print(f"Results saved to {answer_patching_fp}")

def clean_corrupted_prompt_padding(model, clean_str_tokens, clean_r_start_idx, clean_r_end_idx, corrupted_str_tokens, corrupted_r_start_idx, corrupted_r_end_idx):
    clean_len, corrupted_len = len(clean_str_tokens), len(corrupted_str_tokens)
    if clean_len == corrupted_len and clean_r_start_idx == corrupted_r_start_idx and clean_r_end_idx == corrupted_r_end_idx:
        return clean_str_tokens, corrupted_str_tokens
    else:
        query_len = max(clean_r_start_idx, corrupted_r_start_idx) # pre <think>
        reasoning_len = max(clean_r_end_idx - clean_r_start_idx, corrupted_r_end_idx - corrupted_r_start_idx) + 1 # [<think>, ....,  </think>]
        answer_len = max(clean_len - clean_r_end_idx - 1, corrupted_len - corrupted_r_end_idx - 1) # post </think>
        tot_len = query_len + reasoning_len + answer_len

        # Create lists for padded tokens
        clean_str_tokens_padded = [model.tokenizer.pad_token] * tot_len
        corrupted_str_tokens_padded = [model.tokenizer.pad_token] * tot_len
        
        # Add think tags
        clean_str_tokens_padded[query_len] = '<think>'
        corrupted_str_tokens_padded[query_len] = '<think>'

        eot_token_idx = query_len + reasoning_len - 1
        clean_str_tokens_padded[eot_token_idx] = '</think>'
        corrupted_str_tokens_padded[eot_token_idx] = '</think>'
        # clean_str_tokens_padded[eot_token_idx] = ' #'
        # corrupted_str_tokens_padded[eot_token_idx] = ' #'

        # Copy query part
        clean_query_offset = query_len - clean_r_start_idx
        corrupted_query_offset = query_len - corrupted_r_start_idx
        
        for i in range(clean_r_start_idx):
            if i < clean_r_start_idx and i + clean_query_offset >= 0:
                clean_str_tokens_padded[i + clean_query_offset] = clean_str_tokens[i]
                
        for i in range(corrupted_r_start_idx):
            if i < corrupted_r_start_idx and i + corrupted_query_offset >= 0:
                corrupted_str_tokens_padded[i + corrupted_query_offset] = corrupted_str_tokens[i]
        
        # Copy reasoning part (between <think> and </think>) 
        clean_str_tokens_padded[(eot_token_idx-(clean_r_end_idx-(clean_r_start_idx+1))):eot_token_idx] = clean_str_tokens[clean_r_start_idx+1:clean_r_end_idx]
        corrupted_str_tokens_padded[(eot_token_idx-(corrupted_r_end_idx-(corrupted_r_start_idx+1))):eot_token_idx] = corrupted_str_tokens[corrupted_r_start_idx+1:corrupted_r_end_idx]

        # # Copy answer part
        clean_answer_tokens = clean_len - (clean_r_end_idx+1)
        clean_str_tokens_padded[-clean_answer_tokens:] = clean_str_tokens[-clean_answer_tokens:]
        corrupted_answer_tokens = corrupted_len - (corrupted_r_end_idx+1)
        corrupted_str_tokens_padded[-corrupted_answer_tokens:] = corrupted_str_tokens[-corrupted_answer_tokens:]

        return clean_str_tokens_padded, corrupted_str_tokens_padded    


### Hooks
def hook_patch_pos_start_end_resid(
    corrupted_residual_component: Float[torch.Tensor, "batch pos d_model"],
    hook,
    pos_start,
    pos_end,
    clean_cache
):
    corrupted_residual_component[:, pos_start:pos_end, :] = clean_cache[hook.name][:, pos_start:pos_end, :]
    return corrupted_residual_component


def hook_patch_head_vector(
        corrupted_head_vector: Float[torch.Tensor, "batch pos head_index d_head"],
        hook,
        head_index,
        l_pos_start_end,
        clean_cache,
    ):
        if l_pos_start_end is None:
            corrupted_head_vector[:, :, head_index, :] = clean_cache[hook.name][:, :, head_index, :]
        else:
            for pos_start, pos_end in l_pos_start_end:
                corrupted_head_vector[:, pos_start:pos_end, head_index, :] = clean_cache[hook.name][
                    :, pos_start:pos_end, head_index, :
                ]
        return corrupted_head_vector

# def hook_patch_answer_resid(
#     corrupted_residual_component: Float[torch.Tensor, "batch pos d_model"],
#     hook,
#     pos_start,
#     clean_cache
# ):
#     corrupted_residual_component[:, pos_start:, :] = clean_cache[hook.name][:, pos_start:, :]
#     return corrupted_residual_component

# def hook_patch_reasoning_resid(
#     corrupted_residual_component: Float[torch.Tensor, "batch pos d_model"],
#     hook,
#     pos_start,
#     pos_end,
#     clean_cache
# ):
#     corrupted_residual_component[:, pos_start:pos_end, :] = clean_cache[hook.name][:, pos_start:pos_end, :]
#     return corrupted_residual_component

# def hook_patch_query_resid(
#     corrupted_residual_component: Float[torch.Tensor, "batch pos d_model"],
#     hook,
#     pos_end,
#     clean_cache
# ):
#     corrupted_residual_component[:, :pos_end, :] = clean_cache[hook.name][:, :pos_end, :]
#     return corrupted_residual_component