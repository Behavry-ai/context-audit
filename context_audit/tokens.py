"""Token estimation with optional tiktoken precision."""
from __future__ import annotations

import json
from typing import Any

# Try to use tiktoken for exact counts; fall back to character approximation
_encoder = None
_method = "estimate"

try:
    import tiktoken
    _encoder = tiktoken.encoding_for_model("gpt-4")
    _method = "tiktoken"
except ImportError:
    pass


def estimate_tokens(obj: Any) -> int:
    """
    Estimate the token count for a JSON-serializable object.

    Uses tiktoken if available (~exact), otherwise character-based
    approximation (~5% variance).
    """
    if isinstance(obj, str):
        text = obj
    else:
        text = json.dumps(obj, separators=(",", ":"))

    if _encoder is not None:
        return len(_encoder.encode(text))

    # Character-based approximation: ~4 chars per token for English + JSON
    return len(text) // 4


def get_method() -> str:
    """Return which token counting method is active."""
    return _method
