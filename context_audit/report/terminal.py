"""Rich terminal report output."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from context_audit.models import AnalysisReport

RISK_COLORS = {
    "low": "green",
    "medium": "yellow",
    "high": "red",
    "critical": "bold red",
}


def render_terminal(report: AnalysisReport, verbose: bool = False) -> None:
    """Render the analysis report to the terminal using Rich."""
    console = Console()

    # ── Header ──
    console.print()
    console.print(Panel(
        "[bold]BEHAVRY CONTEXT LOAD ASSESSMENT[/bold]\n"
        f"Generated: {report.scan_timestamp}\n"
        f"Token method: {report.token_method}",
        border_style="bright_blue",
        width=65,
    ))

    # ── Summary ──
    console.print("\n[bold]SUMMARY[/bold]")
    console.print("─" * 40)
    console.print(f"  Total MCP servers scanned:      {len(report.servers):>6}")
    errored = sum(1 for s in report.servers if s.error)
    if errored:
        console.print(f"  Servers with errors:            {errored:>6}", style="red")
    console.print(f"  Total tools discovered:         {report.total_tools:>6}")
    console.print(f"  Total schema tokens loaded:     {report.total_tokens:>6,}")
    console.print(f"  Estimated monthly token cost:   ${report.monthly_cost_estimate:>8,.0f}  (at ${report.model_price}/1M input tokens)")
    risk_color = RISK_COLORS.get(report.risk_score, "white")
    console.print(f"  Risk score:                     [{risk_color}]{report.risk_score.upper()}[/{risk_color}]")

    # ── Per-Server Breakdown ──
    console.print("\n[bold]PER-SERVER BREAKDOWN[/bold]")
    table = Table(show_header=True, header_style="bold", show_lines=False, pad_edge=False)
    table.add_column("Server", min_width=20)
    table.add_column("Tools", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("% of Total", justify="right")
    table.add_column("Largest Tool")

    for srv in report.servers:
        if srv.error:
            table.add_row(srv.server, "—", "—", "—", f"[red]Error: {srv.error[:40]}[/red]")
            continue

        pct = (srv.raw_tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
        # Find largest tool for this server
        server_tools = [t for t in report.analyzed_tools if t.server == srv.server]
        largest = max(server_tools, key=lambda t: t.tokens) if server_tools else None
        largest_str = f"{largest.name} ({largest.tokens:,})" if largest else "—"

        table.add_row(
            srv.server,
            str(len(srv.tools)),
            f"{srv.raw_tokens:,}",
            f"{pct:.1f}%",
            largest_str,
        )

    console.print(table)

    # ── Waste Analysis ──
    console.print("\n[bold]WASTE ANALYSIS[/bold]")
    console.print("─" * 40)
    d_count = len(report.destructive_tools)
    d_pct = (d_count / report.total_tools * 100) if report.total_tools > 0 else 0
    console.print(f"  Destructive tools exposed:      {d_count:>6}  ({d_pct:.1f}%)")
    console.print("    └─ delete, destroy, purge, remove, execute operations", style="dim")

    w_count = len(report.write_tools)
    w_pct = (w_count / report.total_tools * 100) if report.total_tools > 0 else 0
    console.print(f"  Write tools exposed:            {w_count:>6}  ({w_pct:.1f}%)")
    console.print("    └─ create, update, modify operations loaded into every session", style="dim")

    h_count = len(report.high_token_tools)
    h_pct = (h_count / report.total_tools * 100) if report.total_tools > 0 else 0
    h_tokens = sum(t.tokens for t in report.high_token_tools)
    h_token_pct = (h_tokens / report.total_tokens * 100) if report.total_tokens > 0 else 0
    console.print(f"  High-token tools (>2,000):      {h_count:>6}  ({h_pct:.1f}%)")
    console.print(f"    └─ consuming {h_tokens:,} tokens ({h_token_pct:.1f}% of total)", style="dim")

    if report.waste_percentage > 30:
        console.print(
            f"\n  If your agents primarily read/search, up to {report.waste_percentage:.0f}% of loaded",
            style="yellow",
        )
        console.print("  capabilities may be unnecessary context overhead.", style="yellow")

    # ── Risk Exposure ──
    if report.destructive_tools:
        console.print("\n[bold]RISK EXPOSURE[/bold]")
        console.print("─" * 40)
        console.print("  Tools with destructive semantics visible to all agents:\n")
        shown = report.destructive_tools[:10]
        for tool in shown:
            console.print(f"  ⚠  {tool.server}:{tool.name}", style="yellow", end="")
            console.print(f"  ({tool.tokens:,} tokens)", style="dim")
        remaining = len(report.destructive_tools) - len(shown)
        if remaining > 0:
            console.print(f"  ... and {remaining} more", style="dim")
        console.print(
            "\n  These tools expand attack surface and consume tokens even if",
            style="dim",
        )
        console.print("  your agents never invoke them.", style="dim")

    # ── Compression Simulation ──
    if report.compression_simulations:
        console.print("\n[bold]COMPRESSION SIMULATION[/bold]")
        console.print("─" * 40)
        console.print("  If schema governance were applied:\n")

        sim_table = Table(show_header=True, header_style="bold", show_lines=False, pad_edge=False)
        sim_table.add_column("Verbosity Level", min_width=18)
        sim_table.add_column("Tokens", justify="right")
        sim_table.add_column("Savings", justify="right")
        sim_table.add_column("Monthly Cost", justify="right")

        for level_name in ("full", "compact", "minimal", "policy_filtered"):
            sim = report.compression_simulations.get(level_name)
            if not sim:
                continue
            display_name = level_name.replace("_", " ").title()
            if level_name == "policy_filtered":
                display_name += "*"
            cost = (sim.tokens * report.sessions_per_month * report.model_price) / 1_000_000
            savings = f"{sim.savings_pct:.1f}%" if sim.savings_pct > 0 else "—"
            sim_table.add_row(
                display_name if level_name != "full" else f"{display_name} (current)",
                f"{sim.tokens:,}",
                savings,
                f"${cost:,.0f}",
            )

        console.print(sim_table)
        console.print(
            "\n  * Policy-filtered: read-only agent profile, destructive tools",
            style="dim",
        )
        console.print("    hidden, compact verbosity on remaining tools.", style="dim")

        # Savings range
        compact_sim = report.compression_simulations.get("compact")
        minimal_sim = report.compression_simulations.get("minimal")
        if compact_sim and minimal_sim:
            console.print(
                f"\n  Projected savings with Behavry Context Gate: "
                f"{compact_sim.savings_pct:.0f}% to {minimal_sim.savings_pct:.0f}%",
                style="bold bright_blue",
            )

    # ── Verbose per-tool breakdown ──
    if verbose and report.analyzed_tools:
        console.print("\n[bold]PER-TOOL BREAKDOWN[/bold]")
        tool_table = Table(show_header=True, header_style="bold", show_lines=False)
        tool_table.add_column("Server")
        tool_table.add_column("Tool")
        tool_table.add_column("Category")
        tool_table.add_column("Tokens", justify="right")

        for tool in sorted(report.analyzed_tools, key=lambda t: t.tokens, reverse=True):
            cat_style = "red" if tool.is_destructive else ("yellow" if tool.is_write else "green")
            tool_table.add_row(
                tool.server,
                tool.name,
                Text(tool.category, style=cat_style),
                f"{tool.tokens:,}",
            )
        console.print(tool_table)

    # ── Footer ──
    console.print()
    console.print(Panel(
        "[bold bright_blue]Context Gate by Behavry[/bold bright_blue]\n"
        "Policy-gated schema governance for MCP.\n\n"
        "Your agents shouldn't see tools they can't use.\n"
        "Context Gate enforces least privilege on the\n"
        "cognitive surface — not just the execution surface.\n\n"
        "Learn more: [link]https://behavry.ai/context-gate[/link]",
        border_style="bright_blue",
        width=65,
    ))
    console.print()
