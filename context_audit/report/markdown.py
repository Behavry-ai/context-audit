"""Markdown report generator."""
from __future__ import annotations

from context_audit.models import AnalysisReport


def render_markdown(report: AnalysisReport) -> str:
    """Render the analysis report as Markdown."""
    lines: list[str] = []

    lines.append("# Behavry Context Load Assessment")
    lines.append("")
    lines.append(f"**Generated:** {report.scan_timestamp}")
    lines.append(f"**Token method:** {report.token_method}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| MCP servers scanned | {len(report.servers)} |")
    lines.append(f"| Total tools discovered | {report.total_tools} |")
    lines.append(f"| Total schema tokens | {report.total_tokens:,} |")
    lines.append(f"| Monthly cost estimate | ${report.monthly_cost_estimate:,.0f} |")
    lines.append(f"| Risk score | **{report.risk_score.upper()}** |")
    lines.append("")

    # Per-server
    lines.append("## Per-Server Breakdown")
    lines.append("")
    lines.append("| Server | Tools | Tokens | % of Total |")
    lines.append("|--------|-------|--------|------------|")
    for srv in report.servers:
        if srv.error:
            lines.append(f"| {srv.server} | — | — | Error: {srv.error[:40]} |")
            continue
        pct = (srv.raw_tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
        lines.append(f"| {srv.server} | {len(srv.tools)} | {srv.raw_tokens:,} | {pct:.1f}% |")
    lines.append("")

    # Waste
    lines.append("## Waste Analysis")
    lines.append("")
    d_count = len(report.destructive_tools)
    w_count = len(report.write_tools)
    lines.append(f"- **Destructive tools exposed:** {d_count}")
    lines.append(f"- **Write tools exposed:** {w_count}")
    lines.append(f"- **High-token tools (>2,000):** {len(report.high_token_tools)}")
    lines.append(f"- **Waste percentage:** {report.waste_percentage:.1f}%")
    lines.append("")

    # Risk
    if report.destructive_tools:
        lines.append("## Risk Exposure")
        lines.append("")
        lines.append("Destructive tools visible to all agents:")
        lines.append("")
        for t in report.destructive_tools[:15]:
            lines.append(f"- ⚠️ `{t.server}:{t.name}` ({t.tokens:,} tokens)")
        remaining = len(report.destructive_tools) - 15
        if remaining > 0:
            lines.append(f"- ... and {remaining} more")
        lines.append("")

    # Compression
    if report.compression_simulations:
        lines.append("## Compression Simulation")
        lines.append("")
        lines.append("| Verbosity Level | Tokens | Savings | Monthly Cost |")
        lines.append("|-----------------|--------|---------|--------------|")
        for level in ("full", "compact", "minimal", "policy_filtered"):
            sim = report.compression_simulations.get(level)
            if not sim:
                continue
            name = level.replace("_", " ").title()
            if level == "full":
                name += " (current)"
            elif level == "policy_filtered":
                name += "*"
            cost = (sim.tokens * report.sessions_per_month * report.model_price) / 1_000_000
            savings = f"{sim.savings_pct:.1f}%" if sim.savings_pct > 0 else "—"
            lines.append(f"| {name} | {sim.tokens:,} | {savings} | ${cost:,.0f} |")
        lines.append("")
        lines.append("\\* Policy-filtered: read-only agent profile, destructive tools hidden, compact verbosity.")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("**[Context Gate by Behavry](https://behavry.ai/context-gate)** — Policy-gated schema governance for MCP.")
    lines.append("")

    return "\n".join(lines)
