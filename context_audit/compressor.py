"""Compression simulation module.

Simulates what a governed schema would look like at different verbosity levels.
Does not modify anything — calculates projected token counts only.
"""
from __future__ import annotations

import json
from typing import Any

from context_audit.tokens import estimate_tokens


def compact_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a compact version of a tool schema.

    Removes description text, keeps param names + types + required only.
    """
    result: dict[str, Any] = {"name": tool.get("name", "")}

    input_schema = tool.get("inputSchema", {})
    if input_schema:
        compact_input: dict[str, Any] = {"type": input_schema.get("type", "object")}
        properties = input_schema.get("properties", {})
        if properties:
            compact_props: dict[str, Any] = {}
            for prop_name, prop_def in properties.items():
                compact_props[prop_name] = {"type": prop_def.get("type", "string")}
                if "enum" in prop_def:
                    compact_props[prop_name]["enum"] = prop_def["enum"]
            compact_input["properties"] = compact_props
        required = input_schema.get("required")
        if required:
            compact_input["required"] = required
        result["inputSchema"] = compact_input

    return result


def minimal_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a minimal version — just name + param names.
    """
    result: dict[str, Any] = {"name": tool.get("name", "")}

    input_schema = tool.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    if properties:
        result["params"] = list(properties.keys())

    return result


def estimate_compact_tokens(tool: dict[str, Any]) -> int:
    """Estimate tokens for a compact schema."""
    return estimate_tokens(compact_schema(tool))


def estimate_minimal_tokens(tool: dict[str, Any]) -> int:
    """Estimate tokens for a minimal schema."""
    return estimate_tokens(minimal_schema(tool))
