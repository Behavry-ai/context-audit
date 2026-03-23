"""Click CLI entry point for context-audit."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from context_audit import __version__


@click.group()
@click.version_option(version=__version__, prog_name="context-audit")
def main() -> None:
    """Behavry Context Audit — Measure the context window cost of your MCP integrations."""
    pass


@main.command()
@click.option("--config", "config_path", type=click.Path(), help="Path to MCP config file")
@click.option("--server", "server_urls", multiple=True, help="MCP server URL (repeatable)")
@click.option("--proxy", "proxy_url", help="Behavry proxy URL (reads upstream server registry)")
@click.option("--format", "fmt", default="terminal", type=click.Choice(["terminal", "markdown", "html", "json"]))
@click.option("--output", "output_path", type=click.Path(), help="Write report to file")
@click.option("--model-price", default=3.0, type=float, help="Token price per 1M input tokens")
@click.option("--sessions", default=1000, type=int, help="Estimated sessions per month")
@click.option("--timeout", default=30, type=int, help="Connection timeout per server (seconds)")
@click.option("--verbose", is_flag=True, help="Show per-tool token breakdown")
@click.option("--discover", is_flag=True, help="Auto-discover MCP configs on this system")
def scan(
    config_path: str | None,
    server_urls: tuple[str, ...],
    proxy_url: str | None,
    fmt: str,
    output_path: str | None,
    model_price: float,
    sessions: int,
    timeout: int,
    verbose: bool,
    discover: bool,
) -> None:
    """Scan MCP servers and produce a context load assessment."""
    from context_audit.config_parser import auto_discover, parse_config
    from context_audit.models import ServerConfig

    servers: list[ServerConfig] = []

    # Collect servers from all sources
    if config_path:
        try:
            servers.extend(parse_config(config_path))
        except Exception as exc:
            click.echo(f"Error parsing config: {exc}", err=True)
            sys.exit(1)

    for url in server_urls:
        name = url.split("/")[-1] or url
        servers.append(ServerConfig(name=name, transport="http", url=url))

    if discover:
        found = auto_discover()
        if found:
            click.echo(f"Discovered {len(found)} MCP config(s):", err=True)
            for client, path in found:
                click.echo(f"  {client}: {path}", err=True)
                try:
                    servers.extend(parse_config(str(path)))
                except Exception as exc:
                    click.echo(f"    Error: {exc}", err=True)
        else:
            click.echo("No MCP configs found on this system.", err=True)

    if not servers:
        click.echo("No servers to scan. Use --config, --server, or --discover.", err=True)
        sys.exit(1)

    click.echo(f"Scanning {len(servers)} MCP server(s)...", err=True)

    # Run scan
    from context_audit.scanner import MCPScanner
    scanner = MCPScanner(timeout=timeout)
    results = asyncio.run(scanner.scan_all(servers))

    # Analyze
    from context_audit.analyzer import ContextAnalyzer
    analyzer = ContextAnalyzer(model_price=model_price, sessions_per_month=sessions)
    report = analyzer.analyze(results)

    # Render
    if fmt == "terminal":
        from context_audit.report.terminal import render_terminal
        render_terminal(report, verbose=verbose)
    elif fmt == "json":
        from context_audit.report.json_export import render_json
        output = render_json(report)
        if output_path:
            Path(output_path).write_text(output)
            click.echo(f"JSON report written to {output_path}", err=True)
        else:
            click.echo(output)
    elif fmt == "markdown":
        from context_audit.report.markdown import render_markdown
        output = render_markdown(report)
        if output_path:
            Path(output_path).write_text(output)
            click.echo(f"Markdown report written to {output_path}", err=True)
        else:
            click.echo(output)
    elif fmt == "html":
        from context_audit.report.html import render_html
        output = render_html(report)
        if output_path:
            Path(output_path).write_text(output)
            click.echo(f"HTML report written to {output_path}", err=True)
        else:
            click.echo(output)


@main.command()
@click.option("--config", "config_path", type=click.Path(), required=True, help="Path to MCP config file")
@click.option("--max-tokens", default=50000, type=int, help="Fail if total schema tokens exceed this")
@click.option("--max-destructive", default=10, type=int, help="Fail if destructive tool count exceeds this")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "terminal"]))
@click.option("--timeout", default=30, type=int, help="Connection timeout per server (seconds)")
def ci(
    config_path: str,
    max_tokens: int,
    max_destructive: int,
    fmt: str,
    timeout: int,
) -> None:
    """CI-friendly mode. Returns exit code 1 if thresholds exceeded."""
    from context_audit.config_parser import parse_config
    from context_audit.scanner import MCPScanner
    from context_audit.analyzer import ContextAnalyzer

    try:
        servers = parse_config(config_path)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if not servers:
        click.echo("No servers found in config.", err=True)
        sys.exit(2)

    scanner = MCPScanner(timeout=timeout)
    results = asyncio.run(scanner.scan_all(servers))

    analyzer = ContextAnalyzer()
    report = analyzer.analyze(results)

    # Output report
    if fmt == "terminal":
        from context_audit.report.terminal import render_terminal
        render_terminal(report)
    else:
        from context_audit.report.json_export import render_json
        click.echo(render_json(report))

    # Check thresholds
    violations: list[str] = []
    if report.total_tokens > max_tokens:
        violations.append(f"Total tokens {report.total_tokens:,} exceeds max {max_tokens:,}")
    if len(report.destructive_tools) > max_destructive:
        violations.append(f"Destructive tools {len(report.destructive_tools)} exceeds max {max_destructive}")

    if violations:
        click.echo("\n⛔ CI CHECK FAILED:", err=True)
        for v in violations:
            click.echo(f"  • {v}", err=True)
        sys.exit(1)
    else:
        click.echo("\n✅ CI check passed", err=True)


@main.command()
@click.argument("before", type=click.Path(exists=True))
@click.argument("after", type=click.Path(exists=True))
@click.option("--format", "fmt", default="terminal", type=click.Choice(["terminal", "markdown", "json"]))
def compare(before: str, after: str, fmt: str) -> None:
    """Compare two JSON scan results to show delta."""
    import json as json_mod
    from pathlib import Path

    before_data = json_mod.loads(Path(before).read_text())
    after_data = json_mod.loads(Path(after).read_text())

    b_tokens = before_data.get("summary", {}).get("total_tokens", 0)
    a_tokens = after_data.get("summary", {}).get("total_tokens", 0)
    delta = a_tokens - b_tokens
    delta_pct = (delta / b_tokens * 100) if b_tokens > 0 else 0

    b_tools = before_data.get("summary", {}).get("total_tools", 0)
    a_tools = after_data.get("summary", {}).get("total_tools", 0)

    b_destructive = before_data.get("waste_analysis", {}).get("destructive_tools", 0)
    a_destructive = after_data.get("waste_analysis", {}).get("destructive_tools", 0)

    if fmt == "terminal":
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="Context Audit Comparison")
        table.add_column("Metric")
        table.add_column("Before", justify="right")
        table.add_column("After", justify="right")
        table.add_column("Delta", justify="right")

        sign = "+" if delta >= 0 else ""
        color = "red" if delta > 0 else "green"
        table.add_row("Total tokens", f"{b_tokens:,}", f"{a_tokens:,}", f"[{color}]{sign}{delta:,} ({sign}{delta_pct:.1f}%)[/{color}]")
        table.add_row("Total tools", str(b_tools), str(a_tools), str(a_tools - b_tools))
        table.add_row("Destructive tools", str(b_destructive), str(a_destructive), str(a_destructive - b_destructive))

        console.print(table)
    elif fmt == "json":
        import json as j
        click.echo(j.dumps({
            "before_tokens": b_tokens,
            "after_tokens": a_tokens,
            "delta_tokens": delta,
            "delta_pct": round(delta_pct, 1),
        }, indent=2))
    else:
        click.echo(f"# Context Audit Comparison\n")
        click.echo(f"| Metric | Before | After | Delta |")
        click.echo(f"|--------|--------|-------|-------|")
        sign = "+" if delta >= 0 else ""
        click.echo(f"| Tokens | {b_tokens:,} | {a_tokens:,} | {sign}{delta:,} ({sign}{delta_pct:.1f}%) |")
        click.echo(f"| Tools | {b_tools} | {a_tools} | {a_tools - b_tools} |")
        click.echo(f"| Destructive | {b_destructive} | {a_destructive} | {a_destructive - b_destructive} |")


if __name__ == "__main__":
    main()
