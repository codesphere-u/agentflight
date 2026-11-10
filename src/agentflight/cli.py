"""
agentflight.cli
===============
Command-Line Interface & Reproducible Benchmark Suite for `agentflight`.

Subcommands:
- `lint`      : Run the 10-rule MCP Tool-Smell Linter on showcase or user JSON tool schemas.
- `demo`      : End-to-end demonstration of flight recording, <1ms replay, circuit breaking, and trajectory diffing.
- `benchmark` : Measure throughput and latency across cassette recording, SHA-256 verification,
                deterministic replay, loop circuit breaking, and 200-tool MCP linting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .diff import compare_cassettes
from .eval import TrajectoryEvaluator
from .guard import CircuitBreakerTripped, TrajectoryCircuitBreaker
from .linter import (
    RULE_CATALOG,
    SHOWCASE_FLAWED_MCP_TOOLS,
    SHOWCASE_HARDENED_MCP_TOOLS,
    ToolSmellLinter,
)
from .mcp_server import AgentFlightMCPServer
from .otel_export import export_cassette_to_otel
from .recorder import CassetteReplayer, FlightRecorder, verify_cassette


def _run_lint_command(args: argparse.Namespace) -> int:
    linter = ToolSmellLinter()

    if args.schema_file:
        raw = json.loads(Path(args.schema_file).read_text(encoding="utf-8"))
        tools = raw.get("tools", raw) if isinstance(raw, dict) else raw
        report = linter.lint(tools)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            _print_lint_report("Custom MCP Tool Suite", report)
        return 0 if report.error_count == 0 else 1

    flawed_report = linter.lint(SHOWCASE_FLAWED_MCP_TOOLS)
    hardened_report = linter.lint(SHOWCASE_HARDENED_MCP_TOOLS)

    if args.json:
        print(
            json.dumps(
                {
                    "flawed_suite": flawed_report.to_dict(),
                    "hardened_suite": hardened_report.to_dict(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    _print_lint_report("Showcase Flawed MCP Tool Suite (Before Hardening)", flawed_report)
    print()
    _print_lint_report("Showcase Hardened MCP Tool Suite (After Remediation)", hardened_report)
    return 0


def _print_lint_report(title: str, report: Any) -> None:
    print(f"=== {title} ===")
    print(
        f"Tools Analyzed: {report.tool_count} | "
        f"Agent Ergonomics Score: {report.ergonomics_score}/100 (Grade {report.grade}) | "
        f"Est. Overhead: {report.estimated_tokens_per_turn} tokens/turn | "
        f"Errors: {report.error_count} | Warnings: {report.warning_count}"
    )
    if not report.findings:
        print("No MCP tool-smell findings detected (10/10 rules passed).")
        return

    print("\n| Rule | Severity | Tool / Scope | Message |")
    print("| :--- | :--- | :--- | :--- |")
    for f in report.findings:
        scope = f"{f.tool_name} ({f.property_path})" if f.property_path else f.tool_name
        print(f"| `{f.rule_id}` | {f.severity.upper()} | `{scope}` | {f.message} |")


def _run_demo_command(args: argparse.Namespace) -> int:
    print("=== AgentFlight End-to-End Reliability Demo ===\n")

    # 1. Record a 5-step incident-response agent trajectory
    recorder = FlightRecorder(
        agent_id="sre-incident-responder-v2",
        metadata={"environment": "production-sim", "incident_id": "INC-2026-8841"},
    )
    recorder.record(
        kind="llm_turn",
        actor="planner_model",
        input_payload={"goal": "Investigate checkout latency spike on service payment-api"},
        output_payload={"plan": ["query_metrics", "fetch_recent_deploys", "rollback_release"]},
        latency_ms=420.5,
        prompt_tokens=610,
        completion_tokens=95,
        cost_usd=0.0024,
    )
    recorder.record(
        kind="mcp_rpc",
        actor="prometheus.query_metrics",
        input_payload={"service": "payment-api", "window": "15m", "metric": "p99_latency_ms"},
        output_payload={"p99_latency_ms": 1840.0, "baseline_ms": 145.0, "anomaly": True},
        latency_ms=88.2,
    )
    recorder.record(
        kind="mcp_rpc",
        actor="github.fetch_recent_deploys",
        input_payload={"repo": "org/payment-api", "limit": 2},
        output_payload={"latest_sha": "9f81c2b", "deployed_minutes_ago": 11},
        latency_ms=112.4,
    )
    recorder.record(
        kind="tool_call",
        actor="k8s.rollback_release",
        input_payload={"deployment": "payment-api", "target_revision": "prev", "dry_run": False},
        output_payload={"rolled_back": True, "active_revision": "8a40d1e"},
        latency_ms=264.0,
    )
    recorder.record(
        kind="llm_turn",
        actor="planner_model",
        input_payload={"observation": "Rollback complete; verify p99 recovery"},
        output_payload={"summary": "Rolled back payment-api to 8a40d1e; latency normalized."},
        latency_ms=355.0,
        prompt_tokens=840,
        completion_tokens=82,
        cost_usd=0.0031,
    )

    verified = verify_cassette(recorder)
    print(
        f"[1/4] Recorded & Verified Golden Cassette: {len(recorder.spans)} steps | "
        f"Head SHA-256: {recorder.head_hash[:16]}... | Chain Valid: {verified}"
    )
    print(
        f"      Live Execution Cost: ${recorder.total_cost_usd:.4f} | "
        f"Live Tokens: {recorder.total_tokens} | Live Latency: {recorder.total_latency_ms:.1f} ms"
    )

    # 2. Replay deterministically in <1ms with $0.00 cost
    replayer = CassetteReplayer(recorder)
    t0 = time.perf_counter()
    for sp in recorder.spans:
        out = replayer.replay_step(sp.kind, sp.actor, sp.input_payload)
        assert out == sp.output_payload
    replay_ms = (time.perf_counter() - t0) * 1000.0
    print(
        f"[2/4] Deterministic Cassette Replay: {len(recorder.spans)} steps replayed in "
        f"{replay_ms:.3f} ms | API Spend: $0.0000 (Saved ${replayer.cost_saved_usd:.4f} & {replayer.tokens_saved} tokens)"
    )

    # 3. Demonstrate Ping-Pong Circuit Breaker (A -> B -> A -> B)
    breaker = TrajectoryCircuitBreaker(max_ping_pong_cycles=2, max_identical_repeats=3)
    oscillation_steps = [
        ("search_logs", {"query": "timeout"}),
        ("refine_query", {"query": "timeout"}),
        ("search_logs", {"query": "timeout"}),
        ("refine_query", {"query": "timeout"}),
    ]
    tripped_exc: Optional[CircuitBreakerTripped] = None
    for tool_name, payload in oscillation_steps:
        try:
            breaker.observe(tool_name, payload)
        except CircuitBreakerTripped as exc:
            tripped_exc = exc
            break

    print(
        f"[3/4] Circuit Breaker Guard: Tripped={breaker.stats.tripped} | "
        f"Reason='{tripped_exc.reason if tripped_exc else 'none'}' at step {tripped_exc.step_index if tripped_exc else -1}"
    )

    # 4. Evaluate a slightly suboptimal candidate trajectory against the golden cassette
    candidate = FlightRecorder(agent_id="sre-incident-responder-candidate")
    for sp in recorder.spans[:3]:
        candidate.record(
            sp.kind,
            sp.actor,
            sp.input_payload,
            sp.output_payload,
            prompt_tokens=sp.prompt_tokens,
            completion_tokens=sp.completion_tokens,
            cost_usd=sp.cost_usd,
        )
    # Extra redundant check before rollback
    candidate.record(
        kind="mcp_rpc",
        actor="prometheus.query_metrics",
        input_payload={"service": "payment-api", "window": "5m", "metric": "p99_latency_ms"},
        output_payload={"p99_latency_ms": 1890.0},
    )
    for sp in recorder.spans[3:]:
        candidate.record(
            sp.kind,
            sp.actor,
            sp.input_payload,
            sp.output_payload,
            prompt_tokens=sp.prompt_tokens,
            completion_tokens=sp.completion_tokens,
            cost_usd=sp.cost_usd,
        )

    diff_report = TrajectoryEvaluator().diff_trajectories(recorder, candidate)
    print(
        f"[4/4] Golden Trajectory Diff: Tool Precision={diff_report.tool_precision:.2f} | "
        f"Recall={diff_report.tool_recall:.2f} | Step Efficiency={diff_report.step_efficiency_ratio:.2f} | "
        f"Goal Completion Score={diff_report.goal_completion_score:.4f} (Passed={diff_report.passed})"
    )
    return 0


def _build_synthetic_200_mcp_tools() -> List[Dict[str, Any]]:
    """Generate a deterministic corpus of 200 MCP tool definitions for benchmarking."""
    tools: List[Dict[str, Any]] = []
    for i in range(200):
        if i % 4 == 0:
            # Flawed destructive tool
            tools.append(
                {
                    "name": f"delete_resource_{i}",
                    "description": "Deletes item",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "flag": {"type": "boolean", "description": "Toggle mode"},
                            "status": {"type": "string", "description": "Resource status"},
                        },
                    },
                }
            )
        else:
            # Well-structured MCP tool
            tools.append(
                {
                    "name": f"fetch_telemetry_metric_{i}",
                    "description": (
                        f"Retrieve aggregated time-series telemetry for service shard #{i} "
                        "within a bounded ISO-8601 time window."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "required": ["service_id", "window"],
                        "properties": {
                            "service_id": {
                                "type": "string",
                                "description": f"Unique identifier of service shard #{i}.",
                            },
                            "window": {
                                "type": "string",
                                "enum": ["5m", "15m", "1h", "24h"],
                                "description": "Aggregation lookback window.",
                            },
                            "include_histograms": {
                                "type": "boolean",
                                "description": "Whether to include p50/p95/p99 latency histograms.",
                            },
                        },
                    },
                }
            )
    return tools


def run_benchmarks() -> Dict[str, Any]:
    """Execute deterministic microbenchmarks and return structured metrics."""
    # 1. Cassette Recording + SHA-256 Chain Verification (1,000 steps)
    rec = FlightRecorder(agent_id="bench-agent")
    t0 = time.perf_counter()
    for i in range(1000):
        rec.record(
            kind="tool_call" if i % 2 == 0 else "llm_turn",
            actor=f"tool_{i % 12}",
            input_payload={"step": i, "query": f"item_{i}", "limit": 10},
            output_payload={"ok": True, "count": i % 5},
            latency_ms=12.5,
            prompt_tokens=150,
            completion_tokens=40,
            cost_usd=0.0005,
        )
    record_1000_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    verify_cassette(rec)
    verify_1000_ms = (time.perf_counter() - t1) * 1000.0

    # 2. Deterministic Cassette Replay Throughput (1,000 steps)
    replayer = CassetteReplayer(rec)
    t2 = time.perf_counter()
    for sp in rec.spans:
        replayer.replay_step(sp.kind, sp.actor, sp.input_payload)
    replay_1000_ms = (time.perf_counter() - t2) * 1000.0
    replay_per_step_us = (replay_1000_ms * 1000.0) / 1000.0

    # 3. Real-Time Circuit Breaker Inspection Latency (1,000 non-looping steps)
    breaker = TrajectoryCircuitBreaker(
        max_identical_repeats=5,
        max_ping_pong_cycles=3,
        max_total_tokens=10_000_000,
        max_cost_usd=10_000.0,
    )
    t3 = time.perf_counter()
    for sp in rec.spans:
        breaker.observe_span(sp)
    guard_1000_ms = (time.perf_counter() - t3) * 1000.0
    guard_per_step_us = (guard_1000_ms * 1000.0) / 1000.0

    # 4. MCP Tool-Smell Linter across 200 Tool Schemas (all 10 rules including pairwise TS008)
    tools_200 = _build_synthetic_200_mcp_tools()
    linter = ToolSmellLinter()
    t4 = time.perf_counter()
    lint_report = linter.lint(tools_200)
    lint_200_ms = (time.perf_counter() - t4) * 1000.0

    # 5. Trajectory Diff Engine on 1,000-step trajectories
    evaluator = TrajectoryEvaluator()
    t5 = time.perf_counter()
    diff_report = evaluator.diff_trajectories(rec, rec)
    diff_1000_ms = (time.perf_counter() - t5) * 1000.0

    return {
        "record_1000_spans_ms": round(record_1000_ms, 2),
        "verify_1000_spans_ms": round(verify_1000_ms, 2),
        "replay_1000_spans_ms": round(replay_1000_ms, 2),
        "replay_per_step_us": round(replay_per_step_us, 2),
        "guard_1000_spans_ms": round(guard_1000_ms, 2),
        "guard_per_step_us": round(guard_per_step_us, 2),
        "lint_200_tools_ms": round(lint_200_ms, 2),
        "lint_200_findings": len(lint_report.findings),
        "diff_1000_spans_ms": round(diff_1000_ms, 2),
        "diff_goal_score": diff_report.goal_completion_score,
    }


def _run_benchmark_command(args: argparse.Namespace) -> int:
    metrics = run_benchmarks()
    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
        return 0

    print("| Subsystem Operation | Workload Size | Total Latency (ms) | Per-Unit Latency | Throughput |")
    print("| :--- | :--- | ---: | ---: | ---: |")
    rec_tp = int(1000.0 / (metrics["record_1000_spans_ms"] / 1000.0))
    ver_tp = int(1000.0 / (metrics["verify_1000_spans_ms"] / 1000.0))
    rep_tp = int(1000.0 / (metrics["replay_1000_spans_ms"] / 1000.0))
    grd_tp = int(1000.0 / (metrics["guard_1000_spans_ms"] / 1000.0))
    lnt_tp = int(200.0 / (metrics["lint_200_tools_ms"] / 1000.0))
    dff_tp = int(1000.0 / (metrics["diff_1000_spans_ms"] / 1000.0))

    print(
        f"| `FlightRecorder.record` (SHA-256 chain) | 1,000 spans | "
        f"{metrics['record_1000_spans_ms']:.2f} ms | "
        f"{metrics['record_1000_spans_ms']:.2f} us/span | {rec_tp:,} spans/s |"
    )
    print(
        f"| `verify_cassette` ( Tamper Verification) | 1,000 spans | "
        f"{metrics['verify_1000_spans_ms']:.2f} ms | "
        f"{metrics['verify_1000_spans_ms']:.2f} us/span | {ver_tp:,} spans/s |"
    )
    print(
        f"| `CassetteReplayer.replay_step` ($0 Stub) | 1,000 spans | "
        f"{metrics['replay_1000_spans_ms']:.2f} ms | "
        f"{metrics['replay_per_step_us']:.2f} us/span | {rep_tp:,} spans/s |"
    )
    print(
        f"| `TrajectoryCircuitBreaker.observe_span` | 1,000 spans | "
        f"{metrics['guard_1000_spans_ms']:.2f} ms | "
        f"{metrics['guard_per_step_us']:.2f} us/span | {grd_tp:,} spans/s |"
    )
    print(
        f"| `ToolSmellLinter.lint` (10 Rules + TS008) | 200 MCP tools | "
        f"{metrics['lint_200_tools_ms']:.2f} ms | "
        f"{(metrics['lint_200_tools_ms'] * 1000.0 / 200.0):.2f} us/tool | {lnt_tp:,} tools/s |"
    )
    print(
        f"| `TrajectoryEvaluator.diff_trajectories` | 1,000 vs 1,000 spans | "
        f"{metrics['diff_1000_spans_ms']:.2f} ms | "
        f"{metrics['diff_1000_spans_ms']:.2f} us/span | {dff_tp:,} spans/s |"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentflight",
        description=(
            "AI Agent Black-Box Flight Recorder, Deterministic Trajectory Replay, "
            "Loop/Cost Circuit Breaker & MCP Tool-Smell Linter"
        ),
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_lint = sub.add_parser(
        "lint",
        help="Run the 10-rule MCP Tool-Smell Linter on a tool schema JSON file or built-in showcase.",
    )
    p_lint.add_argument(
        "--schema-file",
        type=str,
        default=None,
        help="Optional path to a JSON file containing a list of MCP tool definitions.",
    )
    p_lint.add_argument("--json", action="store_true", help="Emit JSON output.")
    p_lint.set_defaults(func=_run_lint_command)

    p_demo = sub.add_parser(
        "demo",
        help="Run an interactive showcase of recording, <1ms replay, circuit breaking, and trajectory diffing.",
    )
    p_demo.set_defaults(func=_run_demo_command)

    p_bench = sub.add_parser(
        "benchmark",
        help="Run reproducible performance benchmarks across all AgentFlight subsystems.",
    )
    p_bench.add_argument("--json", action="store_true", help="Emit JSON benchmark metrics.")
    p_bench.set_defaults(func=_run_benchmark_command)

    p_diff = sub.add_parser(
        "diff",
        help="Compare a baseline cassette against a candidate cassette to detect behavioral regressions.",
    )
    p_diff.add_argument("baseline", type=str, help="Path to baseline .flight.json or .flight.jsonl cassette.")
    p_diff.add_argument("candidate", type=str, help="Path to candidate .flight.json or .flight.jsonl cassette.")
    p_diff.add_argument("--json", action="store_true", help="Emit JSON diff report.")
    p_diff.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.80,
        help="Minimum similarity score before flagging regression (default 0.80).",
    )
    p_diff.set_defaults(func=_run_diff_command)

    p_otel = sub.add_parser(
        "export-otel",
        help="Export a recorded cassette into W3C TraceContext / OpenTelemetry JSON spans for StackPulse.",
    )
    p_otel.add_argument("cassette", type=str, help="Path to .flight.json or .flight.jsonl cassette.")
    p_otel.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output file path for exported OTel JSON spans.",
    )
    p_otel.add_argument(
        "--service-name",
        type=str,
        default=None,
        help="Optional override for OpenTelemetry service_name.",
    )
    p_otel.set_defaults(func=_run_export_otel_command)

    p_http = sub.add_parser(
        "serve-http",
        help="Start the remote HTTP / SSE MCP server for cloud hosting (Glama.ai, Fly.io, Docker).",
    )
    p_http.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    p_http.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    p_http.set_defaults(func=_run_serve_http_command)

    p_mcp = sub.add_parser(
        "serve-mcp",
        help="Start the JSON-RPC 2.0 MCP server over stdio.",
    )
    p_mcp.set_defaults(func=_run_serve_mcp_command)

    return parser


def _run_diff_command(args: argparse.Namespace) -> int:
    report = compare_cassettes(
        baseline=args.baseline,
        candidate=args.candidate,
        similarity_threshold=args.similarity_threshold,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.summary_markdown)
    return 1 if report.regression_detected else 0


def _run_export_otel_command(args: argparse.Namespace) -> int:
    spans = export_cassette_to_otel(
        cassette=args.cassette,
        service_name=args.service_name,
        output_path=args.output,
    )
    if not args.output:
        print(json.dumps(spans, indent=2, sort_keys=True))
    else:
        print(f"Exported {len(spans)} W3C TraceContext / OpenTelemetry spans to {args.output}")
    return 0


def _run_serve_http_command(args: argparse.Namespace) -> int:
    from .http_server import run_http_server
    server = AgentFlightMCPServer()
    httpd = run_http_server(server, host=args.host, port=args.port)
    print(f"AgentFlight HTTP/SSE server running on http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
    return 0


def _run_serve_mcp_command(args: argparse.Namespace) -> int:
    server = AgentFlightMCPServer()
    server.serve_stdio()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
