"""JSON report export."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from context_audit.models import AnalysisReport


def render_json(report: AnalysisReport) -> str:
    """Render the analysis report as JSON."""
    data = _report_to_dict(report)
    return json.dumps(data, indent=2, default=str)


def _report_to_dict(report: AnalysisReport) -> dict[str, Any]:
    """Convert an AnalysisReport to a JSON-serializable dict."""
    return {
        "meta": {
            "tool": "behavry-context-audit",
            "version": "0.1.0",
            "timestamp": report.scan_timestamp,
            "token_method": report.token_method,
        },
        "summary": {
            "total_servers": len(report.servers),
            "total_tools": report.total_tools,
            "total_tokens": report.total_tokens,
            "monthly_cost_estimate": round(report.monthly_cost_estimate, 2),
            "waste_percentage": round(report.waste_percentage, 1),
            "risk_score": report.risk_score,
            "model_price_per_million": report.model_price,
            "sessions_per_month": report.sessions_per_month,
        },
        "servers": [
            {
                "name": s.server,
                "tools": len(s.tools),
                "tokens": s.raw_tokens,
                "scan_duration_ms": round(s.scan_duration_ms, 1),
                "error": s.error,
            }
            for s in report.servers
        ],
        "waste_analysis": {
            "destructive_tools": len(report.destructive_tools),
            "write_tools": len(report.write_tools),
            "high_token_tools": len(report.high_token_tools),
            "destructive_tool_list": [
                {"name": t.name, "server": t.server, "tokens": t.tokens}
                for t in report.destructive_tools
            ],
        },
        "compression": {
            level: {
                "tokens": sim.tokens,
                "savings_pct": sim.savings_pct,
                "tools_included": sim.tools_included,
                "tools_excluded": sim.tools_excluded,
            }
            for level, sim in report.compression_simulations.items()
        },
        "tools": [
            {
                "name": t.name,
                "server": t.server,
                "category": t.category,
                "tokens": t.tokens,
                "is_destructive": t.is_destructive,
            }
            for t in sorted(report.analyzed_tools, key=lambda x: x.tokens, reverse=True)
        ],
    }
