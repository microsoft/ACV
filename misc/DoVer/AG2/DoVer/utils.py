#!/usr/bin/env python3
# Utility helpers for DoVer Azure OpenAI integrations.

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import AzureOpenAI

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

def load_problem_gt(exp_results_dir: Path, sid: str) -> Tuple[str, str]:
    meta_path = exp_results_dir / f"{sid}" / "session_metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {str(meta_path)}")
    meta_obj = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "problem_text" in meta_obj and "ground_truth" in meta_obj, f"Metadata missing required fields in {str(meta_path)}"
    q = meta_obj['problem_text']
    gt = meta_obj["ground_truth"]
    return q, gt

AZURE_OPENAI_ENDPOINT_ENV_VAR = "AZURE_OPENAI_ENDPOINT"
AZURE_OPENAI_API_KEY_ENV_VAR = "AZURE_OPENAI_API_KEY"
AZURE_OPENAI_API_VERSION_ENV_VAR = "AZURE_OPENAI_API_VERSION"
DEFAULT_AZURE_OPENAI_ENDPOINT = os.getenv(AZURE_OPENAI_ENDPOINT_ENV_VAR)
DEFAULT_AZURE_OPENAI_API_VERSION = os.getenv(AZURE_OPENAI_API_VERSION_ENV_VAR, "2024-08-01-preview")


def make_openai_client(
    azure_endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
) -> AzureOpenAI:
    """Create an Azure OpenAI client using key-based authentication."""
    resolved_endpoint = azure_endpoint or DEFAULT_AZURE_OPENAI_ENDPOINT
    if not resolved_endpoint:
        raise RuntimeError(f"{AZURE_OPENAI_ENDPOINT_ENV_VAR} must be set to call the Azure OpenAI API.")

    resolved_api_key = api_key or os.getenv(AZURE_OPENAI_API_KEY_ENV_VAR)
    if not resolved_api_key:
        raise RuntimeError(f"{AZURE_OPENAI_API_KEY_ENV_VAR} must be set to call the Azure OpenAI API.")

    resolved_api_version = api_version or DEFAULT_AZURE_OPENAI_API_VERSION
    return AzureOpenAI(azure_endpoint=resolved_endpoint, api_key=resolved_api_key, api_version=resolved_api_version)
