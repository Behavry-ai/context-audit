"""Data models for context audit scan results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServerConfig:
    """Configuration for a single MCP server to scan."""
    name: str
    transport: str = "http"  # "http" | "stdio"
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None


@dataclass
class ToolSchema:
    """A single tool's schema as returned by tools/list."""
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Result of scanning a single MCP server."""
    server: str
    tools: list[ToolSchema] = field(default_factory=list)
    raw_tokens: int = 0
    scan_duration_ms: float = 0.0
    error: str | None = None


@dataclass
class AnalyzedTool:
    """A tool with classification and token analysis."""
    name: str
    server: str
    category: str  # read, write, delete, execute, unknown
    verb: str
    tokens: int
    is_destructive: bool
    is_write: bool
    description: str = ""


@dataclass
class SimulationResult:
    """Result of a compression simulation at a given verbosity level."""
    tokens: int
    savings_pct: float
    tools_included: int
    tools_excluded: int


@dataclass
class AnalysisReport:
    """Complete analysis report across all scanned servers."""
    scan_timestamp: str
    token_method: str  # "tiktoken" or "estimate"
    total_tools: int = 0
    total_tokens: int = 0
    monthly_cost_estimate: float = 0.0
    servers: list[ScanResult] = field(default_factory=list)
    analyzed_tools: list[AnalyzedTool] = field(default_factory=list)
    destructive_tools: list[AnalyzedTool] = field(default_factory=list)
    write_tools: list[AnalyzedTool] = field(default_factory=list)
    high_token_tools: list[AnalyzedTool] = field(default_factory=list)
    compression_simulations: dict[str, SimulationResult] = field(default_factory=dict)
    waste_percentage: float = 0.0
    risk_score: str = "low"  # low | medium | high | critical
    model_price: float = 3.0  # per 1M input tokens
    sessions_per_month: int = 1000
