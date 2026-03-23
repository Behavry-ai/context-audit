"""Tool verb and category classification.

Classifies MCP tools by their semantic intent based on name patterns.
"""
from __future__ import annotations

from dataclasses import dataclass

VERB_PATTERNS: dict[str, list[str]] = {
    "read": [
        "get", "list", "search", "read", "fetch", "describe", "show",
        "find", "query", "lookup", "view", "inspect", "check", "browse",
        "count", "stat", "info", "status", "who", "where", "which",
    ],
    "write": [
        "create", "add", "post", "insert", "write", "set", "put",
        "update", "edit", "modify", "patch", "rename", "move", "copy",
        "upload", "send", "publish", "submit", "assign", "tag", "label",
        "merge", "approve", "comment", "reply", "share",
    ],
    "delete": [
        "delete", "remove", "destroy", "drop", "purge", "clear",
        "revoke", "unlink", "detach", "archive", "close", "dismiss",
        "reject", "ban", "block",
    ],
    "execute": [
        "execute", "run", "invoke", "trigger", "deploy", "restart",
        "stop", "start", "reboot", "kill", "terminate", "spawn",
        "launch", "apply", "install", "uninstall",
    ],
}

# Flatten for reverse lookup
_VERB_TO_CATEGORY: dict[str, str] = {}
for category, verbs in VERB_PATTERNS.items():
    for verb in verbs:
        _VERB_TO_CATEGORY[verb] = category


@dataclass
class Classification:
    """Result of classifying a tool."""
    category: str  # read, write, delete, execute, unknown
    verb: str      # the matched verb or the raw tool name
    confidence: str  # high, medium, low


def classify_tool(tool_name: str) -> Classification:
    """
    Classify a tool by its name.

    Strategy:
    1. Split the tool name on _ and - separators
    2. Check each word against verb patterns (first match wins)
    3. Also check the full name as a prefix match
    """
    # Normalize: lowercase, split on _ - . /
    parts = tool_name.lower().replace("-", "_").replace(".", "_").replace("/", "_").split("_")

    # Check each part against verb patterns
    for part in parts:
        if part in _VERB_TO_CATEGORY:
            return Classification(
                category=_VERB_TO_CATEGORY[part],
                verb=part,
                confidence="high",
            )

    # Check if the full name starts with a known verb
    lower_name = tool_name.lower()
    for verb, category in _VERB_TO_CATEGORY.items():
        if lower_name.startswith(verb):
            return Classification(
                category=category,
                verb=verb,
                confidence="medium",
            )

    return Classification(
        category="unknown",
        verb=tool_name.split("_")[0] if "_" in tool_name else tool_name,
        confidence="low",
    )
