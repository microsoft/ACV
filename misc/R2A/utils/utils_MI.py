
import transformer_lens.utils as utils
import plotly.express as px
import json
import yaml
import codecs
import numpy as np


def get_topk_head_pos(heatmap, topk=10):
    heatmap_flat = heatmap.flatten()
    topk_indices = np.argsort(heatmap_flat)[-topk:][::-1]  # Get indices of top 5 values
    topk_layers, topk_heads = np.unravel_index(topk_indices, heatmap.shape)
    topk_coords = list(zip(topk_layers, topk_heads))
    topk_values = heatmap_flat[topk_indices]

    return topk_coords, topk_values

def imshow(tensor, **kwargs):
    px.imshow(
        utils.to_numpy(tensor),
        color_continuous_midpoint=0.0,
        color_continuous_scale="RdBu",
        **kwargs,
    ).show()


def line(tensor, **kwargs):
    px.line(
        y=utils.to_numpy(tensor),
        **kwargs,
    ).show()


def scatter(x, y, xaxis="", yaxis="", caxis="", **kwargs):
    x = utils.to_numpy(x)
    y = utils.to_numpy(y)
    px.scatter(
        y=y,
        x=x,
        labels={"x": xaxis, "y": yaxis, "color": caxis},
        **kwargs,
    ).show()


def load_jsonl(file_path):
    """
    Load a JSONL file into a list of dictionaries.
    """
    with open(file_path, 'r') as f:
        data = [json.loads(line) for line in f]
    return data


def load_prompt_response(case_prompt_response_fp):
    def _decode_escapes(obj):
        """Recursively replace escape sequences like '\\n' with real characters."""
        if isinstance(obj, str):
            # Converts \n → newline, \t → tab, \\ → backslash, etc.
            return codecs.decode(obj, "unicode_escape")
        if isinstance(obj, list):
            return [_decode_escapes(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _decode_escapes(v) for k, v in obj.items()}
        return obj

    with open(case_prompt_response_fp, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data = _decode_escapes(data)
    return data
