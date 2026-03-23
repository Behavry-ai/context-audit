"""Waste and risk analysis engine.

Takes raw scan results and produces a complete analysis report with
waste analysis, risk scoring, and compression simulation.
"""
from __future__ import annotations

from datetime import datetime, timezone

from context_audit.classifier import classify_tool
from context_audit.models import (
    AnalysisReport,
    AnalyzedTool,
    ScanResult,
    SimulationResult,
)
from context_audit.tokens import estimate_tokens, get_method


class ContextAnalyzer:
    """Analyzes MCP scan results for waste, risk, and compression opportunities."""

    def __init__(
        self,
        model_price: float = 3.0,
        sessions_per_month: int = 1000,
    ) -> None:
        self.model_price = model_price
        self.sessions_per_month = sessions_per_month

    def analyze(self, results: list[ScanResult]) -> AnalysisReport:
        """Produce a full analysis report from scan results."""
        all_tools: list[AnalyzedTool] = []

        for result in results:
            if result.error:
                continue
            for tool in result.tools:
                classification = classify_tool(tool.name)
                tokens = estimate_tokens(tool.raw)
                all_tools.append(AnalyzedTool(
                    name=tool.name,
                    server=result.server,
                    category=classification.category,
                    verb=classification.verb,
                    tokens=tokens,
                    is_destructive=classification.category in ("delete", "execute"),
                    is_write=classification.category in ("write", "delete", "execute"),
                    description=tool.description[:200] if tool.description else "",
                ))

        total_tokens = sum(t.tokens for t in all_tools)
        write_tools = [t for t in all_tools if t.is_write]
        destructive_tools = [t for t in all_tools if t.is_destructive]
        high_token_tools = sorted(
            [t for t in all_tools if t.tokens > 2000],
            key=lambda t: t.tokens,
            reverse=True,
        )

        write_tokens = sum(t.tokens for t in write_tools)
        waste_pct = (write_tokens / total_tokens * 100) if total_tokens > 0 else 0.0

        monthly_cost = (total_tokens * self.sessions_per_month * self.model_price) / 1_000_000

        compression = self._simulate_compression(all_tools, total_tokens)
        risk_score = self._calculate_risk(len(destructive_tools), total_tokens)

        return AnalysisReport(
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
            token_method=get_method(),
            total_tools=len(all_tools),
            total_tokens=total_tokens,
            monthly_cost_estimate=monthly_cost,
            servers=results,
            analyzed_tools=all_tools,
            destructive_tools=destructive_tools,
            write_tools=write_tools,
            high_token_tools=high_token_tools,
            compression_simulations=compression,
            waste_percentage=waste_pct,
            risk_score=risk_score,
            model_price=self.model_price,
            sessions_per_month=self.sessions_per_month,
        )

    def _simulate_compression(
        self,
        tools: list[AnalyzedTool],
        full_tokens: int,
    ) -> dict[str, SimulationResult]:
        """Simulate token counts at different compression levels."""
        if full_tokens == 0:
            empty = SimulationResult(tokens=0, savings_pct=0, tools_included=0, tools_excluded=0)
            return {"full": empty, "compact": empty, "minimal": empty, "policy_filtered": empty}

        # Compact: remove description text, keep input schema
        # Estimate: descriptions are ~40% of total schema tokens
        compact_tokens = int(full_tokens * 0.60)

        # Minimal: remove descriptions + simplify schemas to just param names + types
        # Estimate: ~25% of full schema size
        minimal_tokens = int(full_tokens * 0.25)

        # Policy-filtered: read-only profile — exclude write/delete/execute tools, compact verbosity
        read_only_tools = [t for t in tools if not t.is_write]
        read_only_tokens = sum(t.tokens for t in read_only_tools)
        policy_tokens = int(read_only_tokens * 0.60)  # compact on remaining

        return {
            "full": SimulationResult(
                tokens=full_tokens,
                savings_pct=0.0,
                tools_included=len(tools),
                tools_excluded=0,
            ),
            "compact": SimulationResult(
                tokens=compact_tokens,
                savings_pct=round((1 - compact_tokens / full_tokens) * 100, 1),
                tools_included=len(tools),
                tools_excluded=0,
            ),
            "minimal": SimulationResult(
                tokens=minimal_tokens,
                savings_pct=round((1 - minimal_tokens / full_tokens) * 100, 1),
                tools_included=len(tools),
                tools_excluded=0,
            ),
            "policy_filtered": SimulationResult(
                tokens=policy_tokens,
                savings_pct=round((1 - policy_tokens / full_tokens) * 100, 1),
                tools_included=len(read_only_tools),
                tools_excluded=len(tools) - len(read_only_tools),
            ),
        }

    @staticmethod
    def _calculate_risk(destructive_count: int, total_tokens: int) -> str:
        """Calculate risk score based on exposure."""
        if destructive_count > 10 or total_tokens > 100_000:
            return "critical"
        if destructive_count > 5 or total_tokens > 75_000:
            return "high"
        if destructive_count > 2 or total_tokens > 50_000:
            return "medium"
        return "low"
