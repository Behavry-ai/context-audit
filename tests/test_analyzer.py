"""Tests for the analysis engine."""
from context_audit.analyzer import ContextAnalyzer
from context_audit.models import ScanResult, ToolSchema


def _make_tool(name: str, desc: str = "A tool", schema_size: int = 100) -> ToolSchema:
    """Create a test tool with controlled token size."""
    return ToolSchema(
        name=name,
        description=desc,
        input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        raw={"name": name, "description": desc, "inputSchema": {"type": "object", "properties": {"x" * schema_size: {"type": "string"}}}},
    )


class TestContextAnalyzer:
    def test_basic_analysis(self):
        results = [
            ScanResult(
                server="test-server",
                tools=[
                    _make_tool("list_users"),
                    _make_tool("delete_user"),
                    _make_tool("create_record"),
                ],
                raw_tokens=300,
            ),
        ]
        analyzer = ContextAnalyzer()
        report = analyzer.analyze(results)

        assert report.total_tools == 3
        assert report.total_tokens > 0
        assert len(report.destructive_tools) == 1  # delete_user
        assert len(report.write_tools) == 2  # delete_user + create_record
        assert report.risk_score in ("low", "medium", "high", "critical")

    def test_risk_scoring(self):
        analyzer = ContextAnalyzer()
        assert analyzer._calculate_risk(0, 10000) == "low"
        assert analyzer._calculate_risk(3, 10000) == "medium"
        assert analyzer._calculate_risk(6, 10000) == "high"
        assert analyzer._calculate_risk(11, 10000) == "critical"
        assert analyzer._calculate_risk(0, 100001) == "critical"

    def test_error_servers_skipped(self):
        results = [
            ScanResult(server="broken", error="connection refused"),
            ScanResult(server="ok", tools=[_make_tool("get_data")], raw_tokens=100),
        ]
        analyzer = ContextAnalyzer()
        report = analyzer.analyze(results)
        assert report.total_tools == 1

    def test_compression_simulation(self):
        results = [
            ScanResult(
                server="test",
                tools=[_make_tool("list_items", schema_size=500)],
                raw_tokens=500,
            ),
        ]
        analyzer = ContextAnalyzer()
        report = analyzer.analyze(results)
        sims = report.compression_simulations

        assert "full" in sims
        assert "compact" in sims
        assert "minimal" in sims
        assert "policy_filtered" in sims
        assert sims["compact"].tokens < sims["full"].tokens
        assert sims["minimal"].tokens < sims["compact"].tokens

    def test_monthly_cost(self):
        results = [
            ScanResult(server="test", tools=[_make_tool("get_x")], raw_tokens=100),
        ]
        analyzer = ContextAnalyzer(model_price=3.0, sessions_per_month=1000)
        report = analyzer.analyze(results)
        # Cost = total_tokens * sessions * price / 1M
        assert report.monthly_cost_estimate >= 0
