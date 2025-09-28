
import torch
import pandas as pd
import numpy as np
from dataclasses import dataclass
import os
from tqdm import tqdm
from functools import partial

from transformer_lens import ActivationCache, HookedTransformer, HookedTransformerConfig
from transformer_lens.utils import test_prompt, get_act_name

from attention_analysis import tokenize_parse_text
from activation_patching import clean_corrupted_prompt_padding
from activation_patching import logits_to_ave_logit_diff, normalize_patched_logit_diff, logits_to_metrics
from activation_patching import get_corrupted_average_logit_diff
from activation_patching import hook_patch_pos_start_end_resid, hook_patch_head_vector
from activation_patching import save_patching_results
from utils.utils_MI import imshow, line, scatter

torch.set_grad_enabled(False)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

D_MODEL_ALIAS = {
    'llama-8B': r"deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    'qwen-1p5B': r"deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    'qwen-7B': r"deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
}


@dataclass
class QAPairResult:      
    unique_id: str
    model_alias: str
    case_id: str
    question_a: str
    question_b: str
    comparator: str
    str_answers: list
    gt_a: str
    gt_b: str
    response_a: str
    response_b: str
    answer_a: str
    answer_b: str
    answer_a_index_from_end: int
    answer_b_index_from_end: int

class QAPairPatchingAnalyzer():
    def __init__(self, 
                 qapr: QAPairResult, 
                 model = None,
                 corrupted_avg_logit_diff_fp = r"corrupted_avg_logit_diff_fp.jsonl",
                 fine_grain_patching_fp = r"fine_grain_patching.jsonl",
                 answer_ending_version = 0,
                 probe_phrase_version = 0,
                 is_probe_reasoning = 1,
                 is_probe_answer = 1,
                 is_probe_query = 0,
                 is_include_prior_reasoning = 1,
                 is_save = True,
                 is_debug = False,
                 ):
        self.qapr = qapr
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if model is not None:
            self.model = model
        else:
            self._load_model()
        assert self.model is not None, "Model loading failed."

        self.answer_ending_version = answer_ending_version
        self.probe_phrase_version = probe_phrase_version
        self.probe_phrase = None
        self.is_probe_reasoning = is_probe_reasoning
        self.is_probe_answer = is_probe_answer
        self.is_probe_query = is_probe_query
        self.is_include_prior_reasoning = is_include_prior_reasoning

        self.is_save = is_save
        self.is_debug = is_debug

        self.corrupted_avg_logit_diff_fp = corrupted_avg_logit_diff_fp
        self.fine_grain_patching_fp = fine_grain_patching_fp
        self.scenario_id = f"{self.qapr.unique_id}"
        
        # Initialize member variables
        self.answer_tokens = None
        self.answer_str_tokens = None
        self.clean_tokens = None
        self.clean_str_tokens = None
        self.clean_r_start_idx = None
        self.clean_r_end_idx = None
        self.clean_tot_answer_tokens = None
        self.clean_prompt = None
        self.corrupted_tokens = None
        self.corrupted_str_tokens = None
        self.corrupted_r_start_idx = None
        self.corrupted_r_end_idx = None
        self.corrupted_tot_answer_tokens = None
        self.corrupted_prompt = None

        self.original_len_clean_str_tokens = None
        self.original_len_clean_query = None
        self.original_len_clean_reasoning = None
        self.original_len_clean_answer = None

        self.clean_logits = None
        self.clean_cache = None
        self.clean_average_logit_diff = None
        self.corrupted_average_logit_diff = None

        # for auto patching analysis
        self.answer_ending = None
        self.answer_backoff = None
        self.reasoning_backoff = None

        self.hook_fine_grain_results = None
        self.hook_fine_grain_results_metrics = None
        
    def _load_model(self):
        model_alias = self.qapr.model_alias
        if model_alias not in D_MODEL_ALIAS:
            raise ValueError(f"Model alias {model_alias} not found in D_MODEL_ALIAS.")
        model_path = D_MODEL_ALIAS[model_alias]
        self.model = HookedTransformer.from_pretrained_no_processing(
                    model_path,
                    center_unembed=True,
                    # center_writing_weights=True,
                    fold_ln=True,
                    # refactor_factored_attn_matrices=True,
                    dtype=torch.bfloat16,
                    device=self.device,
                )

    def _update_token_params(self):
        self.clean_tokens, self.clean_str_tokens, self.clean_r_start_idx, self.clean_r_end_idx, self.clean_tot_answer_tokens = tokenize_parse_text(self.clean_prompt, self.model, prepend_bos=True)
        self.corrupted_tokens, self.corrupted_str_tokens, self.corrupted_r_start_idx, self.corrupted_r_end_idx, self.corrupted_tot_answer_tokens = tokenize_parse_text(self.corrupted_prompt, self.model, prepend_bos=True)

    def pre_processing(self):
        # Use the class's qapr attribute instead of the undefined qapr variable
        # self.clean_prompt = self.qapr.response_a[:self.qapr.answer_a_index_from_end]' /
        # self.corrupted_prompt = self.qapr.response_b[:self.qapr.answer_b_index_from_end]
        self.clean_prompt = self.qapr.response_a[:max(-15, self.qapr.answer_a_index_from_end)]
        self.corrupted_prompt = self.qapr.response_b[:max(-15, self.qapr.answer_b_index_from_end)]

        # Handle the answers containing multiple tokens
        clean_gt_token = self.model.to_tokens(self.qapr.str_answers[0], prepend_bos=False)[0, 0]
        corrupted_gt_token = self.model.to_tokens(self.qapr.str_answers[1], prepend_bos=False)[0, 0]
        self.answer_tokens = [(clean_gt_token, corrupted_gt_token)]
        self.answer_str_tokens = [(self.model.to_str_tokens(clean_gt_token)[0], self.model.to_str_tokens(corrupted_gt_token)[0])]
        self.answer_tokens = torch.tensor(self.answer_tokens).to(self.device)

        # Get token params
        self._update_token_params()

    def align_answer_ending_format(self):
        """
        Align the answer ending format for both clean and corrupted prompts.
        This is necessary because the answer part may have different formats in the two prompts.
        """
        
        answer_ending_template = None
        if self.answer_ending_version == 0:
            answer_ending_template = "Thus, the {} one is \\boxed{{"
        else:
            raise ValueError("answer_ending_version should be 0.")


        self.answer_ending = answer_ending_template.format(self.qapr.comparator)

        curr_last_sentence = self.clean_prompt.split("\n\n")[-1] # TODO: to refine
        assert len(curr_last_sentence) < 300, "The last sentence of the clean prompt is too long, something might be wrong."
        # assert r"\boxed{" in curr_last_sentence, "The last sentence of the clean prompt should contain '\\boxed{'"
        curr_last_sentence_idx = self.clean_prompt.rindex(curr_last_sentence) 
        self.clean_prompt = self.clean_prompt[:curr_last_sentence_idx] + self.answer_ending

        curr_last_sentence = self.corrupted_prompt.split("\n\n")[-1] # TODO: to refine
        assert len(curr_last_sentence) < 300, "The last sentence of the corrupted prompt is too long, something might be wrong."
        # assert r"\boxed{" in curr_last_sentence, "The last sentence of the corrupted prompt should contain '\\boxed{'"
        curr_last_sentence_idx = self.corrupted_prompt.rindex(curr_last_sentence)
        self.corrupted_prompt = self.corrupted_prompt[:curr_last_sentence_idx] + self.answer_ending

        self._update_token_params()

    def trim_reasoning_ending_format(self):
        """
        Trim the reasoning ending format for both clean and corrupted prompts.
        This is necessary because the reasoning part may have different formats in the two prompts.
        """
        assert "</think>" in self.clean_prompt, "The clean prompt should contain '</think>'"
        r_ending_idx = self.clean_prompt.index("</think>")
        curr_last_sentence = self.clean_prompt[:r_ending_idx].split("\n\n")[-1]
        if r"\boxed" in curr_last_sentence:
            curr_last_sentence_idx = self.clean_prompt.index(curr_last_sentence)
            self.clean_prompt = self.clean_prompt[:curr_last_sentence_idx] + self.clean_prompt[r_ending_idx:]

        assert "</think>" in self.corrupted_prompt, "The corrupted prompt should contain '</think>'"
        r_ending_idx = self.corrupted_prompt.index("</think>")
        curr_last_sentence = self.corrupted_prompt[:r_ending_idx].split("\n\n")[-1]
        if r"\boxed" in curr_last_sentence:
            curr_last_sentence_idx = self.corrupted_prompt.index(curr_last_sentence)
            self.corrupted_prompt = self.corrupted_prompt[:curr_last_sentence_idx] + self.corrupted_prompt[r_ending_idx:]

        self._update_token_params()

    def padding(self):
        self.original_len_clean_str_tokens = len(self.clean_str_tokens)
        self.original_len_clean_query = self.clean_r_start_idx
        self.original_len_clean_reasoning = self.clean_r_end_idx - self.clean_r_start_idx - 1 # exclude <think> and </think>
        self.original_len_clean_answer = self.clean_tot_answer_tokens

        if self.is_debug:
            print("Before padding:")
            df = pd.DataFrame({
                'index': ['clean', 'corrupted'],
                'r_start_idx': [self.clean_r_start_idx, self.corrupted_r_start_idx],
                'r_end_idx': [self.clean_r_end_idx, self.corrupted_r_end_idx],
                'tot_answer_tokens': [self.clean_tot_answer_tokens, self.corrupted_tot_answer_tokens],
                'tot_tokens': [len(self.clean_str_tokens), len(self.corrupted_str_tokens)],
            })
            display(df.head())

        # padding
        clean_str_tokens_padded, corrupted_str_tokens_padded = clean_corrupted_prompt_padding(
            self.model, self.clean_str_tokens, self.clean_r_start_idx, self.clean_r_end_idx, self.corrupted_str_tokens, self.corrupted_r_start_idx, self.corrupted_r_end_idx
        )

        self.clean_prompt = "".join(clean_str_tokens_padded[1:])
        self.corrupted_prompt = "".join(corrupted_str_tokens_padded[1:])
        self.clean_tokens, self.clean_str_tokens, self.clean_r_start_idx, self.clean_r_end_idx, self.clean_tot_answer_tokens = tokenize_parse_text("", self.model, prepend_bos=True, str_tokens=clean_str_tokens_padded) # use 'str_tokens' to avoid re-tokenization
        self.corrupted_tokens, self.corrupted_str_tokens, self.corrupted_r_start_idx, self.corrupted_r_end_idx, self.corrupted_tot_answer_tokens = tokenize_parse_text("", self.model, prepend_bos=True, str_tokens=corrupted_str_tokens_padded)

        if self.is_debug:
            print("After padding:")
            df = pd.DataFrame({
                'index': ['clean', 'corrupted'],
                'r_start_idx': [self.clean_r_start_idx, self.corrupted_r_start_idx],
                'r_end_idx': [self.clean_r_end_idx, self.corrupted_r_end_idx],
                'tot_answer_tokens': [self.clean_tot_answer_tokens, self.corrupted_tot_answer_tokens],
                'tot_tokens': [len(self.clean_str_tokens), len(self.corrupted_str_tokens)],
            })
            display(df.head())

        assert len(self.clean_str_tokens) == len(self.corrupted_str_tokens), "The length of clean and corrupted tokens should be the same after padding."
        assert self.clean_r_start_idx == self.corrupted_r_start_idx, "The start index of the reasoning part should be the same for both prompts."
        assert self.clean_r_end_idx == self.corrupted_r_end_idx, "The end index of the reasoning part should be the same for both prompts."
        assert self.clean_tot_answer_tokens == self.corrupted_tot_answer_tokens, "The total number of answer tokens should be the same for both prompts."
    
    def insert_probe_phrase(self):
        assert len(self.clean_str_tokens) == len(self.corrupted_str_tokens), "The length of clean and corrupted tokens should be the same after padding. Call padding() first."

        probe_phrase_template = None
        if self.probe_phrase_version == 0:
            probe_phrase_template = "Final answer is {}.\n"
        elif self.probe_phrase_version == 1:
            probe_phrase_template = "Final answer is \\boxed{{{}}}.\n"
        elif self.probe_phrase_version == 2:
            probe_phrase_template = "Now I know the final answer.\n" # Not able to flip the answer.
        else:
            raise ValueError("probe_phrase_version should be 0 or 1.")
        
        assert probe_phrase_template is not None, "probe_phrase_template should not be None."
        self.clean_probe_phrase  = probe_phrase_template.format(self.qapr.gt_a)
        self.corrupted_probe_phrase = probe_phrase_template.format(self.qapr.gt_b)

        clean_reasoning_backoff = len(self.model.to_str_tokens(self.clean_probe_phrase ))
        corrupted_reasoning_backoff = len(self.model.to_str_tokens(self.corrupted_probe_phrase))
        assert clean_reasoning_backoff == corrupted_reasoning_backoff, "The reasoning backoff should be the same for both prompts."

        # Insert the probe phrase before the reasoning ending
        if self.is_probe_reasoning:
            if self.is_include_prior_reasoning:
                assert "</think>" in self.clean_prompt, "The clean prompt should contain '</think>'"
                r_ending_idx = self.clean_prompt.index("</think>")
                self.clean_prompt = self.clean_prompt[:r_ending_idx] + self.clean_probe_phrase  + self.clean_prompt[r_ending_idx:]

                assert "</think>" in self.corrupted_prompt, "The corrupted prompt should contain '</think>'"
                r_ending_idx = self.corrupted_prompt.index("</think>")        
                self.corrupted_prompt = self.corrupted_prompt[:r_ending_idx] + self.corrupted_probe_phrase + self.corrupted_prompt[r_ending_idx:]
            else:                
                assert "<think>" in self.clean_prompt, "The clean prompt should contain '<think>'"
                assert "</think>" in self.clean_prompt, "The clean prompt should contain '</think>'"
                r_start_idx = self.clean_prompt.index("<think>")
                r_ending_idx = self.clean_prompt.index("</think>")
                self.clean_prompt = self.clean_prompt[:r_start_idx] + "<think>\n" + self.clean_probe_phrase  + self.clean_prompt[r_ending_idx:]

                assert "<think>" in self.corrupted_prompt, "The corrupted prompt should contain '<think>'"
                assert "</think>" in self.corrupted_prompt, "The corrupted prompt should contain '</think>'"
                r_start_idx = self.corrupted_prompt.index("<think>")
                r_ending_idx = self.corrupted_prompt.index("</think>")
                self.corrupted_prompt = self.corrupted_prompt[:r_start_idx] + "<think>\n" + self.corrupted_probe_phrase + self.corrupted_prompt[r_ending_idx:]

            self.reasoning_backoff = clean_reasoning_backoff

        # Insert the probe phrase before the answer ending
        if self.is_probe_answer:
            assert self.answer_ending is not None, "The answer ending should not be None. Run align_answer_ending_format() first."

            answer_ending_idx = self.clean_prompt.index(self.answer_ending)
            self.clean_prompt = self.clean_prompt[:answer_ending_idx] + self.clean_probe_phrase  + self.clean_prompt[answer_ending_idx:]

            answer_ending_idx = self.corrupted_prompt.index(self.answer_ending)
            self.corrupted_prompt = self.corrupted_prompt[:answer_ending_idx] + self.corrupted_probe_phrase + self.corrupted_prompt[answer_ending_idx:]
        
            self.answer_backoff = len(self.model.to_str_tokens(self.clean_probe_phrase  + self.answer_ending))

        if self.is_debug:
            print("reasoning_backoff:", self.reasoning_backoff)
            print("answer_backoff:", self.answer_backoff)

        if self.is_probe_query:
            raise NotImplementedError("Probe query is not implemented yet.")

        # Update token params
        self._update_token_params()
        if self.is_debug:
            print("After insert_probe_phrase:")
            df = pd.DataFrame({
                'index': ['clean', 'corrupted'],
                'r_start_idx': [self.clean_r_start_idx, self.corrupted_r_start_idx],
                'r_end_idx': [self.clean_r_end_idx, self.corrupted_r_end_idx],
                'tot_answer_tokens': [self.clean_tot_answer_tokens, self.corrupted_tot_answer_tokens],
                'tot_tokens': [len(self.clean_str_tokens), len(self.corrupted_str_tokens)],
            })
            display(df.head())

    def quick_check(self):
        """
        Performs a quick validation check on the clean and corrupted prompts
        to ensure they produce the expected ground truth answers.
        """
        
        print("Quick check for clean prompt:")
        test_prompt(self.clean_prompt, self.answer_str_tokens[0][0], self.model, 
                    prepend_bos=True, prepend_space_to_answer=False)
        
        print("\nQuick check for corrupted prompt:")
        test_prompt(self.corrupted_prompt, self.answer_str_tokens[0][1], self.model, 
                    prepend_bos=True, prepend_space_to_answer=False)

    def calc_corrupted_average_logit_diff(self):
        # Pre-compute corrupted average logit diff for CUDA memory saving
        self.corrupted_average_logit_diff = get_corrupted_average_logit_diff(self.corrupted_avg_logit_diff_fp, self.scenario_id, self.model, self.corrupted_tokens, self.answer_tokens, is_save=self.is_save)
        
    def get_clean_cache(self, l_module_name=["resid_pre"]):
        self.clean_logits, self.clean_cache = self.model.run_with_cache(
            self.clean_tokens,
            names_filter=lambda name: any(module_name in name for module_name in l_module_name),
        )
        # self.clean_average_logit_diff = logits_to_ave_logit_diff(self.clean_logits, self.answer_tokens)
        self.clean_eval_metrics = logits_to_metrics(self.clean_logits, self.answer_tokens)
        self.clean_average_logit_diff = self.clean_eval_metrics["logit_diff"]

    def get_corrupted_cache(self, l_module_name=["resid_pre"]):
        self.corrupted_logits, self.corrupted_cache = self.model.run_with_cache(
            self.corrupted_tokens,
            names_filter=lambda name: any(module_name in name for module_name in l_module_name),
        )
        # self.corrupted_average_logit_diff = logits_to_ave_logit_diff(self.corrupted_logits, self.answer_tokens)   
        self.corrupted_eval_metrics = logits_to_metrics(self.corrupted_logits, self.answer_tokens)
        self.corrupted_average_logit_diff = self.corrupted_eval_metrics["logit_diff"]

    def hook_resid_and_head_vector(self, resid_pos_start, resid_pos_end, resid_module = "resid_pre", l_head_pos_start_end=None, attn_module = "z", is_show=True):
        
        patched_diff = torch.zeros(
            self.model.cfg.n_layers, self.model.cfg.n_heads, device=self.device, dtype=torch.float32
        )

        d_patched_metrics = {}
        for layer in tqdm(range(self.model.cfg.n_layers)):
            for head_index in range(self.model.cfg.n_heads):
                hook_fn_resid = partial(hook_patch_pos_start_end_resid, pos_start=resid_pos_start, pos_end=resid_pos_end, clean_cache=self.clean_cache)
                hook_fn_head = partial(hook_patch_head_vector, head_index=head_index, l_pos_start_end=l_head_pos_start_end,  clean_cache=self.clean_cache)
                patched_logits = self.model.run_with_hooks(
                    self.corrupted_tokens,
                    fwd_hooks=[(get_act_name(attn_module, layer, "attn"), hook_fn_head)] \
                        + [(get_act_name(resid_module, e), hook_fn_resid) for e in range(self.model.cfg.n_layers)],
                    return_type="logits",
                )
                patched_logit_diff = logits_to_ave_logit_diff(patched_logits, self.answer_tokens)

                patched_diff[layer, head_index] = normalize_patched_logit_diff(
                    patched_logit_diff, self.clean_average_logit_diff, self.corrupted_average_logit_diff
                )
                # d_patched_metrics[layer] = logits_to_metrics(patched_logits, self.answer_tokens)

        if is_show:
            imshow(patched_diff, title=f"Logit Difference From Patched Head Output", labels={"x": "Head", "y": "Layer"})

        return patched_diff.detach().cpu().numpy().tolist(), d_patched_metrics

    def hook_head_vector(self, l_pos_start_end=None, attn_module = "z", is_show=True):

        patched_diff = torch.zeros(
            self.model.cfg.n_layers, self.model.cfg.n_heads, device=self.device, dtype=torch.float32
        )
        d_patched_metrics = {}
        for layer in tqdm(range(self.model.cfg.n_layers)):
            for head_index in range(self.model.cfg.n_heads):
                hook_fn = partial(hook_patch_head_vector, head_index=head_index, l_pos_start_end=l_pos_start_end,  clean_cache=self.clean_cache)
                patched_logits = self.model.run_with_hooks(
                    self.corrupted_tokens,
                    fwd_hooks=[(get_act_name(attn_module, layer, "attn"), hook_fn)],
                    return_type="logits",
                )
                patched_logit_diff = logits_to_ave_logit_diff(patched_logits, self.answer_tokens)

                patched_diff[layer, head_index] = normalize_patched_logit_diff(
                    patched_logit_diff, self.clean_average_logit_diff, self.corrupted_average_logit_diff
                )
                # d_patched_metrics[layer] = logits_to_metrics(patched_logits, self.answer_tokens)

        if is_show:
            imshow(patched_diff, title=f"Logit Difference From Patched Head Output", labels={"x": "Head", "y": "Layer"})

        return patched_diff.detach().cpu().numpy().tolist(), d_patched_metrics

    def hook_start_end_resid(self, pos_start, pos_end, module_name = "resid_pre", is_show=True):

        patched_diff = torch.zeros(
            self.model.cfg.n_layers, device=self.device, dtype=torch.float32
        )
        d_patched_metrics = {}
        for layer in range(self.model.cfg.n_layers):    
            hook_fn = partial(hook_patch_pos_start_end_resid, pos_start=pos_start, pos_end=pos_end, clean_cache=self.clean_cache)
            patched_logits = self.model.run_with_hooks(
                self.corrupted_tokens,
                fwd_hooks=[(get_act_name(module_name, layer), hook_fn)],
                return_type="logits",
            )
            patched_logit_diff = logits_to_ave_logit_diff(patched_logits, self.answer_tokens)
            patched_diff[layer] = normalize_patched_logit_diff(
                patched_logit_diff, self.clean_average_logit_diff, self.corrupted_average_logit_diff
            )
            d_patched_metrics[layer] = logits_to_metrics(patched_logits, self.answer_tokens)

        if is_show:
            line(patched_diff)

        return patched_diff.detach().cpu().numpy().tolist(), d_patched_metrics

    def _get_patching_region(self):
        '''
        Caution: Run after padding
        '''
        l_patching_region = [
            [self.corrupted_r_start_idx - self.original_len_clean_query, self.corrupted_r_start_idx], # query
            [self.corrupted_r_end_idx - self.original_len_clean_reasoning, self.corrupted_r_end_idx], # reasoning
            [len(self.corrupted_str_tokens) - self.original_len_clean_answer, len(self.corrupted_str_tokens) - 1], # answer except the last predicting token
        ]
        l_patching_special_tokens = [
            self.corrupted_r_start_idx, # <think>
            self.corrupted_r_end_idx, # </think>
            len(self.corrupted_str_tokens) - 1, # predicting token
        ]
        return l_patching_region, l_patching_special_tokens

    def hook_fine_grain_resid_auto(self, module_name = 'resid_pre', answer_backoff=None, reasoning_backoff=None):
        if answer_backoff is None:
            answer_backoff = self.answer_backoff
        if reasoning_backoff is None:
            reasoning_backoff = self.reasoning_backoff
        self.hook_fine_grain_resid(module_name=module_name, is_reasoning_and_answer_per_token=True, reasoning_backoff=reasoning_backoff, answer_backoff=answer_backoff)

    def hook_fine_grain_resid(self, module_name='resid_pre', step=20, l_patching_region=None, l_patching_special_tokens=None, \
                              is_reasoning_and_answer_per_token=False, reasoning_backoff=None, answer_backoff=None, query_forward=None, reasoning_forward=None):
        if is_reasoning_and_answer_per_token:
            step = 1
            l_patching_region = []

            if self.is_probe_reasoning:
                assert reasoning_backoff < self.original_len_clean_reasoning, f"reasoning_backoff should be less than the original length of clean reasoning.{self.original_len_clean_reasoning}"
                reasoning_backoff = min(reasoning_backoff, self.original_len_clean_reasoning)
                l_patching_region.append([self.corrupted_r_end_idx - reasoning_backoff, self.corrupted_r_end_idx]) # reasoning end

                if reasoning_forward is not None:
                    l_patching_region.append([self.corrupted_r_end_idx - self.original_len_clean_reasoning, self.corrupted_r_end_idx - self.original_len_clean_reasoning + reasoning_forward])

            if self.is_probe_answer or answer_backoff is not None:
                l_patching_region.append([len(self.corrupted_str_tokens) - answer_backoff, len(self.corrupted_str_tokens) - 1]) # answer except the last predicting token

            if self.is_probe_query:
                if query_forward is not None:
                    assert query_forward < self.clean_r_start_idx, f"query_forward should be less than the original length of clean query.{self.clean_r_start_idx}"
                    l_patching_region += [1, 1 + query_forward]

            l_patching_special_tokens = [
                # self.corrupted_r_start_idx, # <think>
                self.corrupted_r_end_idx, # </think>
                len(self.corrupted_str_tokens) - 1, # predicting token
            ]
        else:
            if l_patching_region is None or l_patching_special_tokens is None:
                l_patching_region, l_patching_special_tokens = self._get_patching_region()

        assert l_patching_region is not None or l_patching_special_tokens is not None, "l_patching_region and l_patching_special_tokens should not be None."
        if self.is_debug:
            print("l_patching_region:", l_patching_region)
            print("l_patching_special_tokens:", l_patching_special_tokens)
            print("step:", step)

        d_res = {}
        d_res_metrics = {}
        for i, reg in enumerate(l_patching_region):
            print(f"Processing region {i}: {reg}")
            start_idx, end_idx = reg
            for i in tqdm(range(start_idx, end_idx, step)):
                pos_start, pos_end = i, min(i + step, end_idx)
                d_res[f"region_{pos_start}_{pos_end}"], d_res_metrics[f"region_{pos_start}_{pos_end}"] = self.hook_start_end_resid(pos_start=i, pos_end=i+step, module_name=module_name, is_show=False)

        for pos in l_patching_special_tokens:
            d_res[f"special_token_{pos}_{pos+1}"], d_res_metrics[f"special_token_{pos}_{pos+1}"]  = self.hook_start_end_resid(pos_start=pos, pos_end=pos+1, module_name=module_name, is_show=False)

        self.hook_fine_grain_results = d_res
        self.hook_fine_grain_results_metrics = d_res_metrics

        if self.is_save:
            result_data = {
                "scenario_id": self.scenario_id + "_answer_ending_version_" + str(self.answer_ending_version) \
                    + "_probe_phrase_version_" + str(self.probe_phrase_version) + f"__{self.is_probe_query}_{self.is_probe_reasoning}_{self.is_probe_answer}_{self.is_include_prior_reasoning}",
                "model_alias": self.qapr.model_alias,
                "case_id": self.qapr.case_id,
                
                "answer_ending_version": self.answer_ending_version,
                "answer_ending": self.answer_ending,

                "is_probe_reasoning": self.is_probe_reasoning,
                "is_probe_answer": self.is_probe_answer,
                "is_probe_query": self.is_probe_query,
                "probe_version": self.probe_phrase_version,
                "clean_probe_phrase": self.clean_probe_phrase,
                "corrupted_probe_phrase": self.corrupted_probe_phrase,

                "clean_prompt": self.clean_prompt,
                "corrupted_prompt": self.corrupted_prompt,
                "answer_str_tokens": self.answer_str_tokens,
                "clean_r_start_idx": self.clean_r_start_idx,
                "clean_r_end_idx": self.clean_r_end_idx,
                "corrupted_r_start_idx": self.corrupted_r_start_idx,
                "corrupted_r_end_idx": self.corrupted_r_end_idx,

                "reasoning_backoff": self.reasoning_backoff,
                "answer_backoff": self.answer_backoff,

                "clean_average_logit_diff": self.clean_average_logit_diff,
                "corrupted_average_logit_diff": self.corrupted_average_logit_diff,
                "hook_fine_grain_results": d_res,
                "hook_fine_grain_results_metrics": d_res_metrics,
            }
            save_patching_results(self.fine_grain_patching_fp, self.scenario_id, result_data)


def plot_fine_grain_res(d_plot, d_label=None, qappa=None):

    import numpy as np
    import seaborn as sns
    import matplotlib.pyplot as plt
    from collections import OrderedDict

    # Process the d_res dictionary - sort keys by start position
    def get_sort_key(key):
        parts = key.split('_')
        # Handle both formats: "region_start_end" and "special_token_start_end"
        if parts[0] == 'special':
            return int(parts[2])  # Use the position for special tokens
        else:
            return int(parts[1])  # Use start position for regions

    # Create a complete version of d_res that includes gap regions
    complete_d_res = {}

    # First, add all existing entries
    for key, value in d_plot.items():
        complete_d_res[key] = value

    # Extract positions and identify gaps
    positions = []
    end_positions = []
    for key in d_plot.keys():
        parts = key.split('_')
        if parts[0] == 'special':
            pos = int(parts[2])
            positions.append(pos)
            end_positions.append(pos + 1)  # Special tokens are just one position
        else:
            start = int(parts[1])
            end = int(parts[2])
            positions.append(start)
            end_positions.append(end)

    # Sort the positions
    positions = sorted(set(positions))
    end_positions = sorted(set(end_positions))

    # Create a default tensor with the same length as the values in d_res
    first_value = next(iter(d_plot.values()))
    default_tensor = [-100] * len(first_value)  # Create a list of -100s with the same length

    # Fill in gaps between regions
    all_positions = sorted(set(positions + end_positions))
    for i in range(len(all_positions) - 1):
        start = all_positions[i]
        end = all_positions[i + 1]
        
        # Check if this range is already covered
        key = f"region_{start}_{end}"
        special_key = f"special_token_{start}_{end}"
        
        is_covered = False
        for existing_key in d_plot.keys():
            parts = existing_key.split('_')
            if parts[0] == 'region':
                existing_start = int(parts[1])
                existing_end = int(parts[2])
                if start >= existing_start and end <= existing_end:
                    is_covered = True
                    break
            elif parts[0] == 'special' and int(parts[2]) == start and int(parts[2]) + 1 >= end:
                is_covered = True
                break
        
        # If the range isn't covered, add it with default tensor
        if not is_covered and start != end:
            if end - start == 1 and any(p == start for p in positions):
                # This might be a special token position
                complete_d_res[f"special_token_{start}_{end}"] = default_tensor
            else:
                complete_d_res[f"region_{start}_{end}"] = default_tensor

    # Now sort all keys
    sorted_keys = sorted(complete_d_res.keys(), key=get_sort_key)
    sorted_d_res = OrderedDict([(k, complete_d_res[k]) for k in sorted_keys])

    # Extract positions from the sorted keys
    positions = []
    labels = []
    for key in sorted_keys:
        parts = key.split('_')
        if parts[0] == 'special':
            position= int(parts[2])
        else:
            position =(int(parts[1]))
        positions.append(position)
        if qappa is not None:
            labels.append(f"{position}:'{qappa.clean_str_tokens[position]}' || '{qappa.corrupted_str_tokens[position]}'".replace("\n", "\\n"))
        if d_label is not None:
            if key in d_label:
                labels.append(f"{position}:'{d_label[key]}'".replace("\n", "\\n"))
            else:
                labels.append(f"{position}:'<pad>'")

    # Get the overall span of token positions
    min_pos = min(positions)
    max_pos = max(positions)
    num_layers = len(next(iter(d_plot.values())))

    # Stack the arrays from sorted_d_res into a 2D matrix
    l_arrays = [e for e in sorted_d_res.values()]
    data_matrix = np.vstack(l_arrays).T[::-1,:]  # Transpose and reverse rows

    # Create a larger figure for better visualization
    plt.figure(figsize=(20, 8))

    # Create custom x-tick labels with positions
    x_ticks = np.arange(len(sorted_keys))
    
    if len(labels) == len(sorted_keys):
        x_labels = labels
    else:
        x_labels = [str(pos) for pos in positions]

    # Determine value range for colormap
    vmin = max(-0.05, np.min(data_matrix))
    vmax = min(1.0, np.max(data_matrix))

    # Create heatmap with gap regions included
    ax = sns.heatmap(data_matrix, cmap="viridis", vmin=vmin, vmax=vmax, 
                    xticklabels=x_labels, cbar_kws={'label': 'Patching Impact'})

    # Set x-ticks and labels
    ax.set_xticks(np.arange(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=-90, ha='left', fontsize=10)

    # Y-labels are layer indices (reversed)
    y_labels = [f"{i}" for i in range(data_matrix.shape[0])][::-1]
    ax.set_yticks(np.arange(len(y_labels)))
    ax.set_yticklabels(y_labels, rotation=0)

    # Add y-axis labels on the right side
    ax2 = ax.twinx()
    ax2.set_yticks(ax.get_yticks())
    ax2.set_ybound(ax.get_ybound())
    ax2.set_yticklabels(y_labels[::-1], rotation=0)
    ax2.set_ylabel('')  # No label on right y-axis to avoid duplication

    # Add title and labels
    if qappa is not None:
        clean_logit_diff, corrupted_logit_diff = round(qappa.clean_average_logit_diff, 2), round(qappa.corrupted_average_logit_diff, 2)
        plt.title(f"{qappa.qapr.unique_id}_clean_{str(clean_logit_diff)}_corrupted_{str(corrupted_logit_diff)}", fontsize=16)
    else:
        plt.title(f"Fine-grain Patching Analysis", fontsize=16)
    plt.xlabel('Token Position', fontsize=14)
    plt.ylabel('Layer Index', fontsize=14)
    # plt.legend(loc='upper right')

    # Adjust layout and spacing
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.show()