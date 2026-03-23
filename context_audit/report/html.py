"""HTML report generator.

Produces a single self-contained HTML file with inline CSS.
Designed to be forwarded to leadership.
"""
from __future__ import annotations

from context_audit.models import AnalysisReport

RISK_COLORS = {
    "low": "#16803c",
    "medium": "#d97706",
    "high": "#dc2626",
    "critical": "#991b1b",
}


def render_html(report: AnalysisReport) -> str:
    """Render the analysis report as a self-contained HTML file."""
    risk_color = RISK_COLORS.get(report.risk_score, "#6b7280")

    # Build per-server rows
    server_rows = ""
    for srv in report.servers:
        if srv.error:
            server_rows += f'<tr><td>{srv.server}</td><td colspan="3" style="color:#dc2626">Error: {_esc(srv.error[:60])}</td></tr>\n'
            continue
        pct = (srv.raw_tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
        server_tools = [t for t in report.analyzed_tools if t.server == srv.server]
        largest = max(server_tools, key=lambda t: t.tokens) if server_tools else None
        largest_str = f"{largest.name} ({largest.tokens:,})" if largest else "—"
        server_rows += f'<tr><td>{_esc(srv.server)}</td><td>{len(srv.tools)}</td><td>{srv.raw_tokens:,}</td><td>{pct:.1f}%</td><td>{_esc(largest_str)}</td></tr>\n'

    # Build destructive tools list
    risk_items = ""
    for t in report.destructive_tools[:15]:
        risk_items += f'<li><code>{_esc(t.server)}:{_esc(t.name)}</code> <span class="dim">({t.tokens:,} tokens)</span></li>\n'
    remaining = len(report.destructive_tools) - 15
    if remaining > 0:
        risk_items += f'<li class="dim">... and {remaining} more</li>\n'

    # Compression table
    comp_rows = ""
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
        comp_rows += f'<tr><td>{name}</td><td>{sim.tokens:,}</td><td>{savings}</td><td>${cost:,.0f}</td></tr>\n'

    compact_sim = report.compression_simulations.get("compact")
    minimal_sim = report.compression_simulations.get("minimal")
    savings_range = ""
    if compact_sim and minimal_sim:
        savings_range = f"{compact_sim.savings_pct:.0f}% to {minimal_sim.savings_pct:.0f}%"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Behavry Context Load Assessment</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f9fa; color: #1a1a2e; line-height: 1.6; }}
  .header {{ background: #1B2A4A; color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
  .header .meta {{ font-size: 13px; opacity: 0.7; }}
  .content {{ max-width: 900px; margin: 0 auto; padding: 32px 24px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .kpi {{ background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; text-align: center; }}
  .kpi .num {{ font-size: 28px; font-weight: 800; color: #1B2A4A; }}
  .kpi .label {{ font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }}
  .kpi--risk .num {{ color: {risk_color}; }}
  h2 {{ font-size: 18px; font-weight: 700; color: #1B2A4A; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
  th {{ background: #f3f4f6; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; padding: 10px 14px; text-align: left; }}
  td {{ padding: 10px 14px; border-top: 1px solid #f3f4f6; font-size: 14px; }}
  tr:hover {{ background: #fafbfc; }}
  code {{ font-family: 'SF Mono', Consolas, monospace; font-size: 12px; background: #f3f4f6; padding: 2px 6px; border-radius: 3px; }}
  .dim {{ color: #9ca3af; font-size: 13px; }}
  ul {{ list-style: none; padding: 0; }}
  ul li {{ padding: 6px 0; padding-left: 20px; position: relative; font-size: 14px; }}
  ul li::before {{ content: '⚠'; position: absolute; left: 0; color: #D4A843; }}
  .savings {{ background: #1B2A4A; color: white; padding: 16px 24px; border-radius: 10px; text-align: center; margin: 20px 0; }}
  .savings .num {{ font-size: 24px; font-weight: 800; color: #D4A843; }}
  .footer {{ background: #1B2A4A; color: white; padding: 28px 40px; margin-top: 40px; text-align: center; }}
  .footer a {{ color: #D4A843; text-decoration: none; }}
  .footer a:hover {{ text-decoration: underline; }}
  @media print {{ body {{ background: white; }} .header, .footer {{ break-inside: avoid; }} }}
  @media (max-width: 700px) {{ .kpi-row {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>

<div class="header">
  <h1>Context Load Assessment</h1>
  <div class="meta">Generated: {report.scan_timestamp} &middot; Token method: {report.token_method} &middot; by Behavry Context Audit</div>
</div>

<div class="content">

  <div class="kpi-row">
    <div class="kpi"><div class="num">{report.total_tools}</div><div class="label">Tools Discovered</div></div>
    <div class="kpi"><div class="num">{report.total_tokens:,}</div><div class="label">Schema Tokens</div></div>
    <div class="kpi"><div class="num">${report.monthly_cost_estimate:,.0f}</div><div class="label">Monthly Cost</div></div>
    <div class="kpi kpi--risk"><div class="num">{report.risk_score.upper()}</div><div class="label">Risk Score</div></div>
  </div>

  <h2>Per-Server Breakdown</h2>
  <table>
    <thead><tr><th>Server</th><th>Tools</th><th>Tokens</th><th>% of Total</th><th>Largest Tool</th></tr></thead>
    <tbody>{server_rows}</tbody>
  </table>

  <h2>Waste Analysis</h2>
  <table>
    <thead><tr><th>Metric</th><th>Count</th><th>% of Total</th></tr></thead>
    <tbody>
      <tr><td>Destructive tools (delete, execute)</td><td>{len(report.destructive_tools)}</td><td>{(len(report.destructive_tools) / report.total_tools * 100) if report.total_tools else 0:.1f}%</td></tr>
      <tr><td>Write tools (create, update, delete, execute)</td><td>{len(report.write_tools)}</td><td>{(len(report.write_tools) / report.total_tools * 100) if report.total_tools else 0:.1f}%</td></tr>
      <tr><td>High-token tools (&gt;2,000 tokens)</td><td>{len(report.high_token_tools)}</td><td>{(len(report.high_token_tools) / report.total_tools * 100) if report.total_tools else 0:.1f}%</td></tr>
    </tbody>
  </table>

  {"<h2>Risk Exposure</h2><p>Destructive tools visible to all agents:</p><ul>" + risk_items + "</ul>" if report.destructive_tools else ""}

  <h2>Compression Simulation</h2>
  <table>
    <thead><tr><th>Verbosity Level</th><th>Tokens</th><th>Savings</th><th>Monthly Cost</th></tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
  <p class="dim">* Policy-filtered: read-only agent profile, destructive tools hidden, compact verbosity on remaining.</p>

  {"<div class='savings'>Projected savings with Behavry Context Gate: <span class='num'>" + savings_range + "</span></div>" if savings_range else ""}

</div>

<div class="footer">
  <strong>Context Gate by Behavry</strong><br>
  Policy-gated schema governance for MCP.<br><br>
  Your agents shouldn't see tools they can't use.<br>
  <a href="https://behavry.ai/context-gate">Learn more &rarr; behavry.ai/context-gate</a>
</div>

</body>
</html>"""


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
