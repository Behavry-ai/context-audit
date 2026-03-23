"""MCP server scanner.

Connects to MCP servers and calls tools/list to retrieve tool catalogs.
Supports HTTP (Streamable HTTP) and stdio transports.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from context_audit.models import ScanResult, ServerConfig, ToolSchema
from context_audit.tokens import estimate_tokens

logger = logging.getLogger(__name__)


class MCPScanner:
    """Scans MCP servers to retrieve their tool catalogs."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def scan_server(self, server: ServerConfig) -> ScanResult:
        """Connect to a single MCP server and retrieve its tool catalog."""
        t0 = time.perf_counter()
        try:
            if server.transport == "http":
                tools = await self._scan_http(server)
            elif server.transport == "stdio":
                tools = await self._scan_stdio(server)
            else:
                return ScanResult(
                    server=server.name,
                    error=f"Unknown transport: {server.transport}",
                    scan_duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Calculate token count for all tool schemas
            raw_tokens = sum(estimate_tokens(t.raw) for t in tools)

            return ScanResult(
                server=server.name,
                tools=tools,
                raw_tokens=raw_tokens,
                scan_duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as exc:
            logger.error("Error scanning %s: %s", server.name, exc)
            return ScanResult(
                server=server.name,
                error=str(exc),
                scan_duration_ms=(time.perf_counter() - t0) * 1000,
            )

    async def scan_all(self, servers: list[ServerConfig]) -> list[ScanResult]:
        """Scan all servers concurrently."""
        return await asyncio.gather(
            *[self.scan_server(s) for s in servers],
            return_exceptions=False,
        )

    async def _scan_http(self, server: ServerConfig) -> list[ToolSchema]:
        """Scan an HTTP MCP server."""
        assert server.url
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Step 1: Initialize
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "context-audit", "version": "0.1.0"},
                },
            }
            try:
                resp = await client.post(
                    server.url,
                    json=init_req,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Initialize failed for %s, trying tools/list anyway: %s", server.name, exc)

            # Step 2: tools/list
            list_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
            resp = await client.post(
                server.url,
                json=list_req,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            return self._parse_tools_response(data)

    async def _scan_stdio(self, server: ServerConfig) -> list[ToolSchema]:
        """Scan a stdio MCP server by spawning the process."""
        assert server.command

        cmd_parts = [server.command]
        if server.args:
            cmd_parts.extend(server.args)

        env = {**os.environ}
        if server.env:
            env.update(server.env)

        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            # Send initialize
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "context-audit", "version": "0.1.0"},
                },
            }
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(init_req).encode() + b"\n")
            await proc.stdin.drain()

            # Read initialize response
            init_line = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout)
            if init_line:
                try:
                    json.loads(init_line)
                except json.JSONDecodeError:
                    pass

            # Send initialized notification
            notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            proc.stdin.write(json.dumps(notif).encode() + b"\n")
            await proc.stdin.drain()

            # Send tools/list
            list_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
            proc.stdin.write(json.dumps(list_req).encode() + b"\n")
            await proc.stdin.drain()

            # Read tools/list response
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout)
            if not line:
                raise RuntimeError(f"No response from {server.name}")

            data = json.loads(line)
            return self._parse_tools_response(data)
        finally:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except Exception:
                proc.kill()

    def _parse_tools_response(self, data: dict[str, Any]) -> list[ToolSchema]:
        """Parse a tools/list JSON-RPC response into ToolSchema objects."""
        result = data.get("result", {})
        if isinstance(result, dict):
            raw_tools = result.get("tools", [])
        elif isinstance(result, list):
            raw_tools = result
        else:
            raw_tools = []

        tools: list[ToolSchema] = []
        for t in raw_tools:
            if not isinstance(t, dict):
                continue
            tools.append(ToolSchema(
                name=t.get("name", "unknown"),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                raw=t,
            ))

        return tools
