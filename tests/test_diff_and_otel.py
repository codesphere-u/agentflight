"""
Tests for AgentFlight v1.1.0:
- Trajectory Differential Analyzer & Regression Detector (`src/agentflight/diff.py`)
- OpenTelemetry / W3C TraceContext Span Exporter (`src/agentflight/otel_export.py`)
- CLI subcommands (`agentflight diff` and `agentflight export-otel`)
- MCP Server (`agentflight_diff_cassettes`, `agentflight_export_otel`, `agentflight_lint_tools`, `agentflight_verify_cassette`)
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from agentflight import (
    AgentFlightMCPServer,
    FlightRecorder,
    TrajectoryDiffReport,
    __version__,
    compare_cassettes,
    compute_lcs_length,
    compute_levenshtein_distance,
    export_cassette_to_otel,
)
from agentflight.cli import main as cli_main


def _build_baseline_cassette() -> FlightRecorder:
    rec = FlightRecorder(agent_id="sre-responder-v1", metadata={"model": "claude-3.7-sonnet"})
    rec.record(
        kind="llm_turn",
        actor="planner",
        input_payload={"goal": "Investigate checkout latency spike"},
        output_payload={"plan": ["prometheus.query", "k8s.rollback"]},
        latency_ms=300.0,
        prompt_tokens=400,
        completion_tokens=80,
        cost_usd=0.0020,
    )
    rec.record(
        kind="mcp_rpc",
        actor="prometheus.query",
        input_payload={"service": "checkout", "window": "15m"},
        output_payload={"p99_ms": 1450.0, "anomaly": True},
        latency_ms=65.0,
    )
    rec.record(
        kind="tool_call",
        actor="k8s.rollback",
        input_payload={"deployment": "checkout", "dry_run": False},
        output_payload={"rolled_back": True, "revision": "v42"},
        latency_ms=190.0,
    )
    return rec


def test_version_is_current() -> None:
    import re
    from pathlib import Path

    from agentflight.mcp_server import SERVER_VERSION

    pyproject_text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, flags=re.MULTILINE)
    assert match is not None
    assert __version__ == match.group(1)
    assert SERVER_VERSION == __version__


def test_levenshtein_and_lcs_primitives() -> None:
    seq_a = ["prometheus.query", "github.deploys", "k8s.rollback"]
    seq_b = ["prometheus.query", "k8s.rollback"]
    assert compute_levenshtein_distance(seq_a, seq_b) == 1
    assert compute_lcs_length(seq_a, seq_b) == 2
    assert compute_levenshtein_distance([], seq_b) == 2
    assert compute_lcs_length([], seq_b) == 0


def test_diff_identical_cassettes_no_regression() -> None:
    baseline = _build_baseline_cassette()
    report = compare_cassettes(baseline, baseline)
    assert isinstance(report, TrajectoryDiffReport)
    assert report.regression_detected is False
    assert report.similarity_score == 1.0
    assert report.added_tools == []
    assert report.removed_tools == []
    assert report.cost_delta_pct == 0.0
    assert report.token_delta_pct == 0.0
    assert report.latency_delta_pct == 0.0
    assert "NO REGRESSION (PASSED)" in report.summary_markdown


def test_diff_detects_tool_sequence_divergence() -> None:
    baseline = _build_baseline_cassette()
    candidate = FlightRecorder(agent_id="sre-responder-v2")
    candidate.record(
        kind="llm_turn",
        actor="planner",
        input_payload={"goal": "Investigate checkout latency spike"},
        output_payload={"plan": ["datadog.search", "pagerduty.escalate"]},
        latency_ms=310.0,
        prompt_tokens=400,
        completion_tokens=80,
        cost_usd=0.0020,
    )
    candidate.record(
        kind="mcp_rpc",
        actor="datadog.search",
        input_payload={"query": "checkout"},
        output_payload={"hits": 12},
        latency_ms=70.0,
    )
    candidate.record(
        kind="tool_call",
        actor="pagerduty.escalate",
        input_payload={"service": "checkout"},
        output_payload={"rolled_back": False, "revision": "v43"},
        latency_ms=120.0,
    )
    report = compare_cassettes(baseline, candidate)
    assert report.regression_detected is True
    assert report.similarity_score < 0.80
    assert sorted(report.added_tools) == ["datadog.search", "pagerduty.escalate"]
    assert sorted(report.removed_tools) == ["k8s.rollback", "prometheus.query"]
    assert report.levenshtein_distance == 2


def test_diff_detects_new_tool_error_regression() -> None:
    baseline = _build_baseline_cassette()
    candidate = FlightRecorder(agent_id="sre-responder-err")
    for sp in baseline.spans[:2]:
        candidate.record(
            sp.kind,
            sp.actor,
            sp.input_payload,
            sp.output_payload,
            latency_ms=sp.latency_ms,
            prompt_tokens=sp.prompt_tokens,
            completion_tokens=sp.completion_tokens,
            cost_usd=sp.cost_usd,
        )
    candidate.record(
        kind="tool_call",
        actor="k8s.rollback",
        input_payload={"deployment": "checkout", "dry_run": False},
        output_payload={"error": "RBAC permission denied"},
        latency_ms=190.0,
        status="error",
    )
    report = compare_cassettes(baseline, candidate)
    assert report.regression_detected is True
    assert "k8s.rollback" in report.new_tool_errors
    assert report.structural_output_drift is True


def test_diff_detects_loop_regression() -> None:
    baseline = _build_baseline_cassette()
    candidate = FlightRecorder(agent_id="sre-responder-loop")
    for _ in range(3):
        candidate.record(
            kind="mcp_rpc",
            actor="prometheus.query",
            input_payload={"service": "checkout", "window": "15m"},
            output_payload={"p99_ms": 1450.0, "anomaly": True},
            latency_ms=50.0,
        )
    report = compare_cassettes(baseline, candidate)
    assert report.regression_detected is True
    assert report.loop_regression is not None
    assert "exact_call_loop" in report.loop_regression


def test_diff_detects_cost_and_token_spike_regression() -> None:
    baseline = _build_baseline_cassette()
    candidate = FlightRecorder(agent_id="sre-responder-expensive")
    candidate.record(
        kind="llm_turn",
        actor="planner",
        input_payload={"goal": "Investigate checkout latency spike"},
        output_payload={"plan": ["prometheus.query", "k8s.rollback"]},
        latency_ms=900.0,
        prompt_tokens=1600,
        completion_tokens=400,
        cost_usd=0.0120,
    )
    for sp in baseline.spans[1:]:
        candidate.record(
            sp.kind,
            sp.actor,
            sp.input_payload,
            sp.output_payload,
            latency_ms=sp.latency_ms,
        )
    report = compare_cassettes(
        baseline,
        candidate,
        max_cost_increase_pct=50.0,
        max_token_increase_pct=50.0,
    )
    assert report.regression_detected is True
    assert report.cost_delta_pct == pytest.approx(500.0)
    assert report.token_delta_pct > 200.0


def test_diff_detects_structural_output_drift() -> None:
    baseline = _build_baseline_cassette()
    candidate = FlightRecorder(agent_id="sre-responder-drift")
    for sp in baseline.spans[:2]:
        candidate.record(
            sp.kind,
            sp.actor,
            sp.input_payload,
            sp.output_payload,
            latency_ms=sp.latency_ms,
            prompt_tokens=sp.prompt_tokens,
            completion_tokens=sp.completion_tokens,
            cost_usd=sp.cost_usd,
        )
    # Same tool & args, but output schema changed keys
    candidate.record(
        kind="tool_call",
        actor="k8s.rollback",
        input_payload={"deployment": "checkout", "dry_run": False},
        output_payload={"status_text": "done"},
        latency_ms=190.0,
    )
    report = compare_cassettes(baseline, candidate)
    assert report.structural_output_drift is True
    assert report.regression_detected is True


def test_otel_export_w3c_tracecontext_structure() -> None:
    baseline = _build_baseline_cassette()
    spans = export_cassette_to_otel(baseline, service_name="checkout-sre-agent")
    # 1 root SERVER span + 3 recorded trajectory spans = 4 spans
    assert len(spans) == 4
    root = spans[0]
    assert root["parent_span_id"] is None
    assert len(root["trace_id"]) == 32
    assert len(root["span_id"]) == 16
    assert root["service_name"] == "checkout-sre-agent"
    assert root["status_code"] == "OK"
    assert root["span_kind"] == "SERVER"
    assert root["attributes"]["gen_ai.usage.total_tokens"] == 480

    # Child LLM span
    llm_span = spans[1]
    assert llm_span["trace_id"] == root["trace_id"]
    assert llm_span["parent_span_id"] == root["span_id"]
    assert llm_span["operation_name"] == "llm_turn:planner"
    assert llm_span["operation"] == "llm_turn:planner"

    # Tool/MCP child spans parented under the active LLM turn span
    mcp_span = spans[2]
    assert mcp_span["parent_span_id"] == llm_span["span_id"]
    assert mcp_span["service_name"] == "prometheus"
    assert mcp_span["span_kind"] == "CLIENT"


def test_otel_export_error_status_propagation() -> None:
    rec = FlightRecorder(agent_id="err-agent")
    rec.record(
        kind="tool_call",
        actor="db.migrate",
        input_payload={"version": 2},
        output_payload={"error": "Deadlock detected", "error_type": "DatabaseError"},
        latency_ms=42.5,
        status="error",
    )
    spans = export_cassette_to_otel(rec, include_root_span=True)
    assert spans[0]["status_code"] == "ERROR"
    assert spans[1]["status_code"] == "ERROR"
    assert spans[1]["attributes"]["exception.message"] == "Deadlock detected"
    assert spans[1]["attributes"]["exception.type"] == "DatabaseError"


def test_otel_export_without_root_span_and_file_write(tmp_path: Path) -> None:
    rec = _build_baseline_cassette()
    out_file = tmp_path / "otel_spans.json"
    spans = export_cassette_to_otel(rec, include_root_span=False, output_path=out_file)
    assert len(spans) == 3
    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(loaded) == 3
    assert loaded[0]["operation_name"] == "llm_turn:planner"


def test_cli_diff_subcommand_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _build_baseline_cassette()
    base_path = tmp_path / "baseline.flight.jsonl"
    cand_path = tmp_path / "candidate.flight.jsonl"
    base.save(base_path)
    base.save(cand_path)

    rc = cli_main(["diff", str(base_path), str(cand_path)])
    out_md = capsys.readouterr().out
    assert rc == 0
    assert "NO REGRESSION (PASSED)" in out_md

    rc_json = cli_main(["diff", str(base_path), str(cand_path), "--json"])
    out_json = json.loads(capsys.readouterr().out)
    assert rc_json == 0
    assert out_json["regression_detected"] is False
    assert out_json["similarity_score"] == 1.0


def test_cli_export_otel_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _build_baseline_cassette()
    cassette_path = tmp_path / "trace.flight.json"
    otel_path = tmp_path / "spans.json"
    base.save(cassette_path)

    rc = cli_main(["export-otel", str(cassette_path), "--output", str(otel_path)])
    msg = capsys.readouterr().out
    assert rc == 0
    assert "Exported 4 W3C TraceContext" in msg
    assert otel_path.exists()

    rc_stdout = cli_main(["export-otel", str(cassette_path)])
    spans_stdout = json.loads(capsys.readouterr().out)
    assert rc_stdout == 0
    assert len(spans_stdout) == 4


def test_mcp_server_initialize_and_tools_list() -> None:
    from agentflight import __version__

    server = AgentFlightMCPServer()
    init_resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp is not None
    assert init_resp["result"]["serverInfo"]["version"] == __version__

    list_resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert list_resp is not None
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "agentflight_diff_cassettes" in tool_names
    assert "agentflight_export_otel" in tool_names
    assert "agentflight_lint_tools" in tool_names
    assert "agentflight_verify_cassette" in tool_names


def test_mcp_server_diff_and_export_tools(tmp_path: Path) -> None:
    base = _build_baseline_cassette()
    base_path = tmp_path / "base.flight.json"
    base.save(base_path)

    server = AgentFlightMCPServer()
    diff_resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "agentflight_diff_cassettes",
                "arguments": {
                    "baseline_path": str(base_path),
                    "candidate_path": str(base_path),
                },
            },
        }
    )
    assert diff_resp is not None
    diff_payload = diff_resp["result"]["structuredContent"]
    assert diff_payload["regression_detected"] is False
    assert diff_payload["similarity_score"] == 1.0

    otel_resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "agentflight_export_otel",
                "arguments": {"cassette_path": str(base_path)},
            },
        }
    )
    assert otel_resp is not None
    otel_payload = otel_resp["result"]["structuredContent"]
    assert otel_payload["span_count"] == 4


def test_mcp_server_verify_and_lint_tools(tmp_path: Path) -> None:
    base = _build_baseline_cassette()
    base_path = tmp_path / "verify.flight.json"
    base.save(base_path)

    server = AgentFlightMCPServer()
    ver_resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "agentflight_verify_cassette",
                "arguments": {"cassette_path": str(base_path)},
            },
        }
    )
    assert ver_resp is not None
    assert ver_resp["result"]["structuredContent"]["valid"] is True

    lint_resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "agentflight_lint_tools",
                "arguments": {},
            },
        }
    )
    assert lint_resp is not None
    assert lint_resp["result"]["structuredContent"]["ergonomics_score"] == 100


def test_mcp_server_stdio_loop() -> None:
    server = AgentFlightMCPServer()
    stdin = io.StringIO(
        "\n".join(
            [
                "{bad json",
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            ]
        )
        + "\n"
    )
    stdout = io.StringIO()
    server.serve_stdio(stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["error"]["code"] == -32700
    assert lines[1]["id"] == 1


def test_quickstart_example_runs_end_to_end():
    import runpy
    ns = runpy.run_path("examples/quickstart.py")
    res = ns["main"]()
    assert res["steps_recorded"] == 3
    assert res["cassette_verified"] is True
    assert res["otel_spans"] == 4
    assert res["linter_findings"] > 0
