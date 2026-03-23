"""MCP config file parser.

Parses MCP client configuration files to extract server definitions.
Supports Claude Desktop, Cursor, VS Code (Copilot), Windsurf, and custom formats.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from context_audit.models import ServerConfig

logger = logging.getLogger(__name__)

# Known config file locations by client
CONFIG_LOCATIONS: dict[str, list[str]] = {
    "claude_desktop": [
        "~/.config/claude/claude_desktop_config.json",
        "~/Library/Application Support/Claude/claude_desktop_config.json",
    ],
    "cursor": [
        "~/.cursor/mcp.json",
    ],
    "vscode": [
        ".vscode/mcp.json",
        "~/.vscode/mcp.json",
    ],
    "windsurf": [
        "~/.windsurf/mcp_config.json",
        "~/.codeium/windsurf/mcp_config.json",
    ],
    "claude_code": [
        ".mcp.json",
        "~/.claude/mcp.json",
    ],
}


class ConfigError(Exception):
    """Raised when a config file cannot be parsed."""
    pass


def parse_config(path: str) -> list[ServerConfig]:
    """
    Parse an MCP config file and return server definitions.

    Auto-detects the format based on the JSON structure.
    """
    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {config_path}: {exc}")

    # Auto-detect format
    if "mcpServers" in config:
        return _parse_mcp_servers(config["mcpServers"], str(config_path))
    elif "servers" in config:
        return _parse_vscode_servers(config["servers"], str(config_path))
    else:
        raise ConfigError(
            f"Unrecognized config format in {config_path}. "
            "Expected 'mcpServers' (Claude/Cursor/Windsurf) or 'servers' (VS Code)."
        )


def auto_discover() -> list[tuple[str, Path]]:
    """
    Search for known MCP config files on the system.

    Returns a list of (client_name, path) tuples for configs that exist.
    """
    found: list[tuple[str, Path]] = []
    for client, paths in CONFIG_LOCATIONS.items():
        for p in paths:
            expanded = Path(p).expanduser()
            if expanded.exists():
                found.append((client, expanded))
    return found


def _parse_mcp_servers(servers: dict[str, Any], source: str) -> list[ServerConfig]:
    """Parse the mcpServers format used by Claude Desktop, Cursor, Windsurf."""
    configs: list[ServerConfig] = []

    for name, server_def in servers.items():
        if isinstance(server_def, dict):
            # stdio transport: has "command" key
            if "command" in server_def:
                cmd = server_def["command"]
                args = server_def.get("args", [])
                env = server_def.get("env")
                configs.append(ServerConfig(
                    name=name,
                    transport="stdio",
                    command=cmd,
                    args=args if isinstance(args, list) else [args],
                    env=env,
                ))
            # http transport: has "url" key
            elif "url" in server_def:
                configs.append(ServerConfig(
                    name=name,
                    transport="http",
                    url=server_def["url"],
                ))
            else:
                logger.warning("Skipping server %s in %s: no command or url", name, source)
        else:
            logger.warning("Skipping server %s in %s: unexpected type %s", name, source, type(server_def))

    return configs


def _parse_vscode_servers(servers: dict[str, Any], source: str) -> list[ServerConfig]:
    """Parse the servers format used by VS Code / Copilot."""
    configs: list[ServerConfig] = []

    for name, server_def in servers.items():
        if not isinstance(server_def, dict):
            continue

        transport = server_def.get("type", "stdio")

        if transport == "stdio":
            cmd = server_def.get("command")
            if not cmd:
                logger.warning("Skipping server %s in %s: no command", name, source)
                continue
            configs.append(ServerConfig(
                name=name,
                transport="stdio",
                command=cmd,
                args=server_def.get("args", []),
                env=server_def.get("env"),
            ))
        elif transport in ("http", "sse"):
            url = server_def.get("url")
            if not url:
                logger.warning("Skipping server %s in %s: no url", name, source)
                continue
            configs.append(ServerConfig(
                name=name,
                transport="http",
                url=url,
            ))

    return configs
