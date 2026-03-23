"""Tests for MCP config file parser."""
import json
import tempfile
from pathlib import Path

from context_audit.config_parser import parse_config, ConfigError
import pytest


class TestConfigParser:
    def test_parse_claude_desktop_format(self, tmp_path):
        config = {
            "mcpServers": {
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "test"},
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        servers = parse_config(str(config_file))
        assert len(servers) == 2
        assert servers[0].name == "github"
        assert servers[0].transport == "stdio"
        assert servers[0].command == "npx"
        assert servers[0].env == {"GITHUB_TOKEN": "test"}

    def test_parse_vscode_format(self, tmp_path):
        config = {
            "servers": {
                "my-server": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["server.py"],
                },
                "remote": {
                    "type": "http",
                    "url": "https://mcp.example.com",
                },
            }
        }
        config_file = tmp_path / "mcp.json"
        config_file.write_text(json.dumps(config))

        servers = parse_config(str(config_file))
        assert len(servers) == 2

        stdio_srv = next(s for s in servers if s.name == "my-server")
        assert stdio_srv.transport == "stdio"

        http_srv = next(s for s in servers if s.name == "remote")
        assert http_srv.transport == "http"
        assert http_srv.url == "https://mcp.example.com"

    def test_parse_http_in_mcp_servers(self, tmp_path):
        config = {
            "mcpServers": {
                "remote": {"url": "https://mcp.example.com"},
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        servers = parse_config(str(config_file))
        assert len(servers) == 1
        assert servers[0].transport == "http"

    def test_missing_file_raises(self):
        with pytest.raises(ConfigError, match="not found"):
            parse_config("/nonexistent/path.json")

    def test_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        with pytest.raises(ConfigError, match="Invalid JSON"):
            parse_config(str(bad_file))

    def test_unknown_format_raises(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"something": "else"}))
        with pytest.raises(ConfigError, match="Unrecognized"):
            parse_config(str(config_file))
