import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from collections import Counter
import torch
import re
from typing import List, Tuple, Optional


def tokenize_parse_text(text, model, str_tokens=None, prepend_bos=False):
    if str_tokens is None:
        tokens = model.to_tokens(text, prepend_bos=prepend_bos)
        str_tokens = model.to_str_tokens(tokens)
    else:
        tokens = [model.to_single_token(e) for e in str_tokens]
        tokens = torch.tensor(tokens).unsqueeze(0).to(model.cfg.device)
    
    # Identify reasoning and answer sections
    try:
        r_start_idx, r_end_idx = str_tokens.index("<think>"), str_tokens.index("</think>")
    except Exception as e:
        # Handle the case where <think> or </think> is not found
        print(f"Error: {e}")
        print(f"Tokens: {str_tokens}")
        raise ValueError("Reasoning section not found in the text.")
    
    # r_start_idx, r_end_idx = str_tokens.index("<think>"), str_tokens.index(" #")
    tot_answer_tokens = tokens.shape[1] - r_end_idx - 2

    assert r_start_idx < r_end_idx, "Invalid reasoning section indices"
    assert r_end_idx < tokens.shape[1], "End index exceeds token length"
    assert r_start_idx > 0, "Start index must be greater than 0"
    
    return tokens, str_tokens, r_start_idx, r_end_idx, tot_answer_tokens

def get_raw_attention_patterns(text, model, pattern_hook_names_filter=None):

    attn_raw = {}

    def _get_attention_hook(pattern, hook):
        attn_raw[hook.layer()] = pattern.detach().cpu().numpy()

    if pattern_hook_names_filter is None:
        pattern_hook_names_filter = lambda name: name.endswith("pattern")

    # Run the model with the hook
    _ = model.run_with_hooks(
        model.to_tokens(text), 
        return_type=None,
        fwd_hooks=[(
            pattern_hook_names_filter,
            _get_attention_hook
        )]
    )

    return attn_raw

def get_attention_pattern_by_top_head(tokens, model, d_top_head_index_by_layer, pattern_hook_names_filter=None):
    '''
    The goal of this func to obtain the attention pattern of the top attention heads.
    "d_top_head_index_by_layer" is a dictionary that contains the top attention head index for each layer.
    The key is the layer index and the value is a list of top head indices.
    For example, if the top head indices for layer 0 are [1, 2], then d_top_head_index_by_layer[0] = [1, 2].
    '''

    ret = {}

    def _get_attention_hook(pattern, hook):
        if hook.layer() not in d_top_head_index_by_layer:
            return
        top_head_indices = d_top_head_index_by_layer[hook.layer()]
        for head_idx in top_head_indices:
            ret[f"{hook.layer()}_{head_idx}"] = pattern[0, head_idx].detach().cpu().numpy()
        
    if pattern_hook_names_filter is None:
        pattern_hook_names_filter = lambda name: name.endswith("pattern")

    # Run the model with the hook
    _ = model.run_with_hooks(
        tokens,
        return_type=None,
        fwd_hooks=[(
            pattern_hook_names_filter,
            _get_attention_hook
        )]
    )
    return ret


def get_attention_pattern_by_layer(tokens, model, pattern_hook_names_filter=None):

    attn_layer = {}

    def _get_attention_hook(pattern, hook):
        d_tmp = {}
        d_tmp['mean'] = pattern[0].mean(dim=0).detach().cpu().numpy()
        # d_tmp['P5'] = pattern[0].quantile(0.5, dim=0).detach().cpu().numpy()
        # d_tmp['P25'] = pattern[0].quantile(0.25, dim=0).detach().cpu().numpy()
        # d_tmp['P50'] = pattern[0].quantile(0.5, dim=0).detach().cpu().numpy()
        # d_tmp['P75'] = pattern[0].quantile(0.75, dim=0).detach().cpu().numpy()
        # d_tmp['P95'] = pattern[0].quantile(0.95, dim=0).detach().cpu().numpy()
        attn_layer[hook.layer()] = d_tmp

    if pattern_hook_names_filter is None:
        pattern_hook_names_filter = lambda name: name.endswith("pattern")

    # Run the model with the hook
    _ = model.run_with_hooks(
        tokens,
        return_type=None,
        fwd_hooks=[(
            pattern_hook_names_filter,
            _get_attention_hook
        )]
    )

    return attn_layer


def get_natural_attention_weights_by_layer_head(text, model, split_num=5, pattern_hook_names_filter=None):
    '''
    The goal of this func is to find out the attention weights from a source region to a target region.
    Steps to get the source and target region:
    1. Find out 'split_num' indexes that evenly split the interval of [r_start_idx, len(str_tokens)]
    2. With that indexes, say 'l_idx_sep', the total of the source and target region is defined as [r_start_idx, l_idx_sep[i]] for each idx in 'l_idx_sep'.
    3. The split between the source and target region is defined by the current region ratio of 'reasoning' and 'answer' tokens.
    '''
    
    tokens, str_tokens, r_start_idx, r_end_idx, tot_answer_tokens = tokenize_parse_text(text, model)
    
    # Step 1: Find evenly spaced indices that split the interval [r_start_idx, len(str_tokens)]
    token_length = len(str_tokens)
    l_idx_sep = np.linspace(r_start_idx, token_length-1, split_num+1, dtype=int)[1:]  # exclude start index
    
    attention_weights = {}
    
    # For each split point
    for i, split_idx in enumerate(l_idx_sep):
        # Step 3: Calculate the split between source and target based on current reasoning/answer ratio
        reasoning_tokens = r_end_idx - r_start_idx        
        reasoning_ratio = reasoning_tokens / (reasoning_tokens + tot_answer_tokens)
        
        # Define source and target regions
        total_tokens = split_idx - r_start_idx
        split_point = r_start_idx + int(total_tokens * reasoning_ratio)
        target_region = (r_start_idx, split_point)
        source_region = (split_point, split_idx)
        
        # Dictionary to store attention weights for this split
        split_attention = {}
        split_attention_self = {}
        split_attention_prompt = {}
        
        def _attention_hook(pattern, hook):
            # Calculate mean attention from source to target
            weights = pattern[:,:,source_region[0]:source_region[1], target_region[0]:target_region[1]].sum(dim=3).mean(dim=2)
            split_attention[hook.layer()] = weights[0].detach().cpu().numpy()
            
            weights = pattern[:,:,source_region[0]:source_region[1], source_region[0]:source_region[1]].sum(dim=3).mean(dim=2)
            split_attention_self[hook.layer()] = weights[0].detach().cpu().numpy()

            weights = pattern[:,:,source_region[0]:source_region[1], 1:r_start_idx].sum(dim=3).mean(dim=2)
            split_attention_prompt[hook.layer()] = weights[0].detach().cpu().numpy()
        
        if pattern_hook_names_filter is None:
            pattern_hook_names_filter = lambda name: name.endswith("pattern")
        
        # Run the model with the hook
        _ = model.run_with_hooks(
            tokens,
            return_type=None,
            fwd_hooks=[(
                pattern_hook_names_filter,
                _attention_hook
            )]
        )
        
        # Store results for this split
        attention_weights[f'split_{i+1}'] = {
            'source_region': source_region,
            'target_region': target_region,
            'attention': split_attention,
            'attention_self': split_attention_self,
            'attention_prompt': split_attention_prompt
        }
    
    return attention_weights, r_start_idx, r_end_idx, token_length

    


def get_attention_pattern_by_layer_head(text, model, answer_ratio_region=(0., 1), pattern_hook_names_filter=None):
    
    tokens, str_tokens, r_start_idx, r_end_idx, tot_answer_tokens = tokenize_parse_text(text, model)
    
    answer_token_region = r_end_idx + 1 + int(tot_answer_tokens * answer_ratio_region[0]), r_end_idx + 1 + int(tot_answer_tokens * answer_ratio_region[1])

    a2r_mean_all = {}
    a2p_mean_all = {}    
    a2a_mean_all = {}
    r2r_mean_all = {}
    r2p_mean_all = {}

    a2bos_mean_all = {}
    a2bot_mean_all = {}
    a2eot_mean_all = {}

    r2bos_mean_all = {}
    r2bot_mean_all = {}
    def _get_answer_to_reasoning_hook(pattern, hook):

        a2r_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_start_idx+1:r_end_idx].sum(dim=3).mean(dim=2)
        a2p_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], 1:r_start_idx].sum(dim=3).mean(dim=2)
        a2a_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], (r_end_idx+1):-1].sum(dim=3).mean(dim=2)

        a2bos_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], 0:1].sum(dim=3).mean(dim=2)
        a2bot_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_start_idx:r_start_idx+1].sum(dim=3).mean(dim=2)
        a2eot_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_end_idx:r_end_idx+1].sum(dim=3).mean(dim=2)

        r2r_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, r_start_idx+1:r_end_idx].sum(dim=3).mean(dim=2)
        r2p_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, 1:r_start_idx].sum(dim=3).mean(dim=2)

        r2bos_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, 0:1].sum(dim=3).mean(dim=2)
        r2bot_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, r_start_idx:r_start_idx+1].sum(dim=3).mean(dim=2)

        # Store the mean attention to reasoning section for each layer
        a2r_mean_all[hook.layer()] = a2r_mean_tmp[0].detach().cpu().numpy()
        a2p_mean_all[hook.layer()] = a2p_mean_tmp[0].detach().cpu().numpy()
        a2a_mean_all[hook.layer()] = a2a_mean_tmp[0].detach().cpu().numpy()

        a2bos_mean_all[hook.layer()] = a2bos_mean_tmp[0].detach().cpu().numpy()
        a2bot_mean_all[hook.layer()] = a2bot_mean_tmp[0].detach().cpu().numpy()
        a2eot_mean_all[hook.layer()] = a2eot_mean_tmp[0].detach().cpu().numpy()

        r2r_mean_all[hook.layer()] = r2r_mean_tmp[0].detach().cpu().numpy()
        r2p_mean_all[hook.layer()] = r2p_mean_tmp[0].detach().cpu().numpy()

        r2bos_mean_all[hook.layer()] = r2bos_mean_tmp[0].detach().cpu().numpy()
        r2bot_mean_all[hook.layer()] = r2bot_mean_tmp[0].detach().cpu().numpy()

    if pattern_hook_names_filter is None:
        pattern_hook_names_filter = lambda name: name.endswith("pattern")

    # Run the model with the hook
    _ = model.run_with_hooks(
        tokens, 
        return_type=None,
        fwd_hooks=[(
            pattern_hook_names_filter,
            _get_answer_to_reasoning_hook
        )]
    )

    
    a2r_mean = []
    for k, v in a2r_mean_all.items():
        a2r_mean.append(v)
    a2r_mean = np.array(a2r_mean)

    a2p_mean = []
    for k, v in a2p_mean_all.items():
        a2p_mean.append(v)
    a2p_mean = np.array(a2p_mean)

    a2a_mean = []
    for k, v in a2a_mean_all.items():
        a2a_mean.append(v)
    a2a_mean = np.array(a2a_mean)

    r2r_mean = []
    for k, v in r2r_mean_all.items():
        r2r_mean.append(v)
    r2r_mean = np.array(r2r_mean)

    r2p_mean = []
    for k, v in r2p_mean_all.items():
        r2p_mean.append(v)
    r2p_mean = np.array(r2p_mean)

    a2bos_mean = []
    for k, v in a2bos_mean_all.items():
        a2bos_mean.append(v)
    a2bos_mean = np.array(a2bos_mean)

    a2bot_mean = []
    for k, v in a2bot_mean_all.items():
        a2bot_mean.append(v)
    a2bot_mean = np.array(a2bot_mean)

    a2eot_mean = []
    for k, v in a2eot_mean_all.items():
        a2eot_mean.append(v)
    a2eot_mean = np.array(a2eot_mean)

    r2bos_mean = []
    for k, v in r2bos_mean_all.items():
        r2bos_mean.append(v)
    r2bos_mean = np.array(r2bos_mean)

    r2bot_mean = []
    for k, v in r2bot_mean_all.items():
        r2bot_mean.append(v)
    r2bot_mean = np.array(r2bot_mean)

    return a2r_mean, a2p_mean, a2a_mean, r2r_mean, r2p_mean, len(str_tokens), r_start_idx, r_end_idx, answer_token_region, a2bos_mean, a2bot_mean, a2eot_mean, r2bos_mean, r2bot_mean



def get_avg_per_token_attention_pattern_by_layer_head(text, model, answer_ratio_region=(0., 1), pattern_hook_names_filter=None):
    
    tokens, str_tokens, r_start_idx, r_end_idx, tot_answer_tokens = tokenize_parse_text(text, model)
    
    answer_token_region = r_end_idx + 1 + int(tot_answer_tokens * answer_ratio_region[0]), r_end_idx + 1 + int(tot_answer_tokens * answer_ratio_region[1])

    a2r_mean_all = {}
    a2p_mean_all = {}    
    a2a_mean_all = {}
    r2r_mean_all = {}
    r2p_mean_all = {}

    a2bos_mean_all = {}
    a2bot_mean_all = {}
    a2eot_mean_all = {}

    r2bos_mean_all = {}
    r2bot_mean_all = {}
    def _get_answer_to_reasoning_hook(pattern, hook):

        a2r_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_start_idx+1:r_end_idx].mean(dim=3).mean(dim=2)
        a2p_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], 1:r_start_idx].mean(dim=3).mean(dim=2)

        
        a2a_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], (r_end_idx+1):-1].mean(dim=3).mean(dim=2)

        # a2a_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], (r_end_idx+1):-1].sum(dim=3)
        # # consider the average over preceding answer tokens
        # answer_token_len_seq = np.arange(1, answer_token_region[1] - answer_token_region[0] + 1)
        # answer_token_len_seq = torch.tensor(answer_token_len_seq).unsqueeze(0).to(pattern.device)
        # a2a_mean_tmp = a2a_mean_tmp / answer_token_len_seq
        # # average over all answer tokens
        # a2a_mean_tmp = a2a_mean_tmp.mean(dim=2)

        a2bos_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], 0:1].mean(dim=3).mean(dim=2)
        a2bot_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_start_idx:r_start_idx+1].mean(dim=3).mean(dim=2)
        a2eot_mean_tmp = pattern[:,:,answer_token_region[0]:answer_token_region[1], r_end_idx:r_end_idx+1].mean(dim=3).mean(dim=2)

        # r2r_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, r_start_idx+1:r_end_idx].sum(dim=3)
        # # consider the average over preceding reasoning tokens
        # reasoning_token_len_seq = np.arange(1, r_end_idx - r_start_idx)
        # reasoning_token_len_seq = torch.tensor(reasoning_token_len_seq).unsqueeze(0).to(pattern.device)
        # r2r_mean_tmp = r2r_mean_tmp / reasoning_token_len_seq
        # # average over all reasoning tokens
        # r2r_mean_tmp = r2r_mean_tmp.mean(dim=2)

        # r2p_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, 1:r_start_idx].mean(dim=3).mean(dim=2)

        # r2bos_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, 0:1].mean(dim=3).mean(dim=2)
        # r2bot_mean_tmp = pattern[:,:,r_start_idx+1:r_end_idx, r_start_idx:r_start_idx+1].mean(dim=3).mean(dim=2)

        # Store the mean attention to reasoning section for each layer
        a2r_mean_all[hook.layer()] = a2r_mean_tmp[0].detach().cpu().numpy()
        a2p_mean_all[hook.layer()] = a2p_mean_tmp[0].detach().cpu().numpy()
        a2a_mean_all[hook.layer()] = a2a_mean_tmp[0].detach().cpu().numpy()

        a2bos_mean_all[hook.layer()] = a2bos_mean_tmp[0].detach().cpu().numpy()
        a2bot_mean_all[hook.layer()] = a2bot_mean_tmp[0].detach().cpu().numpy()
        a2eot_mean_all[hook.layer()] = a2eot_mean_tmp[0].detach().cpu().numpy()

        # r2r_mean_all[hook.layer()] = r2r_mean_tmp[0].detach().cpu().numpy()
        # r2p_mean_all[hook.layer()] = r2p_mean_tmp[0].detach().cpu().numpy()

        # r2bos_mean_all[hook.layer()] = r2bos_mean_tmp[0].detach().cpu().numpy()
        # r2bot_mean_all[hook.layer()] = r2bot_mean_tmp[0].detach().cpu().numpy()

    if pattern_hook_names_filter is None:
        pattern_hook_names_filter = lambda name: name.endswith("pattern")

    # Run the model with the hook
    _ = model.run_with_hooks(
        tokens, 
        return_type=None,
        fwd_hooks=[(
            pattern_hook_names_filter,
            _get_answer_to_reasoning_hook
        )]
    )

    
    a2r_mean = []
    for k, v in a2r_mean_all.items():
        a2r_mean.append(v)
    a2r_mean = np.array(a2r_mean)

    a2p_mean = []
    for k, v in a2p_mean_all.items():
        a2p_mean.append(v)
    a2p_mean = np.array(a2p_mean)

    a2a_mean = []
    for k, v in a2a_mean_all.items():
        a2a_mean.append(v)
    a2a_mean = np.array(a2a_mean)

    r2r_mean = []
    for k, v in r2r_mean_all.items():
        r2r_mean.append(v)
    r2r_mean = np.array(r2r_mean)

    r2p_mean = []
    for k, v in r2p_mean_all.items():
        r2p_mean.append(v)
    r2p_mean = np.array(r2p_mean)

    a2bos_mean = []
    for k, v in a2bos_mean_all.items():
        a2bos_mean.append(v)
    a2bos_mean = np.array(a2bos_mean)

    a2bot_mean = []
    for k, v in a2bot_mean_all.items():
        a2bot_mean.append(v)
    a2bot_mean = np.array(a2bot_mean)

    a2eot_mean = []
    for k, v in a2eot_mean_all.items():
        a2eot_mean.append(v)
    a2eot_mean = np.array(a2eot_mean)

    r2bos_mean = []
    for k, v in r2bos_mean_all.items():
        r2bos_mean.append(v)
    r2bos_mean = np.array(r2bos_mean)

    r2bot_mean = []
    for k, v in r2bot_mean_all.items():
        r2bot_mean.append(v)
    r2bot_mean = np.array(r2bot_mean)

    return a2r_mean, a2p_mean, a2a_mean, r2r_mean, r2p_mean, len(str_tokens), r_start_idx, r_end_idx, answer_token_region, a2bos_mean, a2bot_mean, a2eot_mean, r2bos_mean, r2bot_mean


def plot_attention_pattern(uid, attn_matrix, title_prefix="Attention Pattern"):
    plt.figure(figsize=(8, 6))
    
    # Normalize the colormap to the full range [0, 1]
    vmin, vmax = 0, 1
    
    ax = sns.heatmap(attn_matrix, 
                     cmap='viridis', 
                     annot=False, 
                     fmt='.3f',
                     vmin=vmin,
                     vmax=vmax,
                     cbar_kws={'label': f'Mean {title_prefix}'})

    plt.xlabel('Attention Head')
    plt.ylabel('Layer')
    plt.title(f'{title_prefix} by Layer and Head: {uid}')

    # Set ticks for better readability
    plt.xticks(np.arange(0, attn_matrix.shape[1], 1), labels=np.arange(0, attn_matrix.shape[1], 1))
    plt.yticks(np.arange(0, attn_matrix.shape[0], 1), labels=range(attn_matrix.shape[0]))

    # Add gridlines to make it easier to identify specific (layer, head) pairs
    ax.grid(True)

    plt.tight_layout()
    plt.show()


# Function to find top-k layer-head combinations across all examples
def analyze_top_attention_patterns(d_attention, k=10):
    # Dictionary to store all top-k positions for each example
    all_top_patterns = {}
    
    # Counter to track frequency of each layer-head combination
    pattern_counter = Counter()
    
    # Process each example
    for uid, attn_matrix in d_attention.items():
        # Flatten the matrix and find top-k indices
        flat_indices = np.argsort(attn_matrix.flatten())[-k:][::-1]
        
        # Convert flat indices to 2D coordinates (layer, head)
        top_k_positions = [(idx // attn_matrix.shape[1], idx % attn_matrix.shape[1]) for idx in flat_indices]
        all_top_patterns[uid] = top_k_positions
        
        # Update the counter
        pattern_counter.update(top_k_positions)
    
    # Find the overall most common layer-head combinations
    most_common = pattern_counter.most_common(k)
    
    # Create a heatmap data
    n_layers = max(pos[0] for pos in pattern_counter.keys()) + 1
    n_heads = max(pos[1] for pos in pattern_counter.keys()) + 1
    heatmap_data = np.zeros((n_layers, n_heads))
    
    for (layer, head), count in pattern_counter.items():
        heatmap_data[layer, head] = count
        
    return {
        'all_patterns': all_top_patterns,
        'most_common': most_common,
        'heatmap_data': heatmap_data
    }