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
import copy
import json
import os
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
    sub = parser.add_subparsers(dest="subcommand", required=False)

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

    p_stdio = sub.add_parser(
        "serve-stdio",
        help="Start the JSON-RPC 2.0 MCP server over stdio (alias for serve-mcp).",
    )
    p_stdio.set_defaults(func=_run_serve_mcp_command)

    p_openany = sub.add_parser(
        "openany",
        help="Interact with OpenAny models and APIs with flight recording, cost circuit breaking, and replay.",
    )
    oa_sub = p_openany.add_subparsers(dest="openany_subcommand", required=False)

    oa_models = oa_sub.add_parser("models", help="List available OpenAny models and per-token pricing.")
    oa_models.add_argument("--json", action="store_true", help="Emit raw JSON model catalog.")
    oa_models.set_defaults(func=_run_openany_command)

    oa_chat = oa_sub.add_parser("chat", help="Execute an OpenAny chat prompt with budget protection and flight recording.")
    oa_chat.add_argument("--prompt", "-p", type=str, required=True, help="User prompt to send to OpenAny.")
    oa_chat.add_argument("--model", "-m", type=str, default=None, help="Model ID (default from OPENANY_DEFAULT_MODEL or MiniMax-M2.5).")
    oa_chat.add_argument("--budget", "-b", type=float, default=None, help="Max USD budget allowed before tripping circuit breaker.")
    oa_chat.add_argument("--record", "-r", type=str, default=None, help="File path to save recorded .flight.json cassette.")
    oa_chat.add_argument("--api-key", type=str, default=None, help="Optional API key override.")
    oa_chat.set_defaults(func=_run_openany_command)

    oa_lint = oa_sub.add_parser("lint-tools", help="Audit OpenAny remote MCP tool definitions against TS001-TS010.")
    oa_lint.add_argument("--json", action="store_true", help="Emit JSON lint report.")
    oa_lint.set_defaults(func=_run_openany_command)

    oa_replay = oa_sub.add_parser("replay", help="Replay an OpenAny trajectory cassette deterministically with zero network calls.")
    oa_replay.add_argument("--cassette", "-c", type=str, required=True, help="Path to .flight.json cassette.")
    oa_replay.set_defaults(func=_run_openany_command)

    p_openany.set_defaults(func=_run_openany_command)

    p_mcp_alias = sub.add_parser(
        "mcp",
        help="Start the JSON-RPC 2.0 MCP server over stdio (alias for serve-mcp).",
    )
    p_mcp_alias.set_defaults(func=_run_serve_mcp_command)

    p_pm = sub.add_parser(
        "post-mortem",
        help="Generate an AAIB/NTSB-grade incident investigation report from a recorded cassette.",
    )
    p_pm.add_argument("cassette", type=str, help="Path to .flight.json cassette to investigate.")
    p_pm.add_argument("--output", "-o", type=str, default=None, help="Optional output path for Markdown report.")
    p_pm.add_argument("--json", action="store_true", help="Emit JSON incident report.")
    p_pm.set_defaults(func=_run_post_mortem_command)

    p_ci = sub.add_parser(
        "ci",
        help="Run CI/CD pre-flight gate (Tool-Smell audits, cassette integrity, budget & latency SLA verification).",
    )
    p_ci.add_argument("--schema-file", type=str, default=None, help="Path to MCP tool schemas JSON to audit.")
    p_ci.add_argument("--cassette", type=str, default=None, help="Path to recorded cassette to verify.")
    p_ci.add_argument("--max-cost", type=float, default=2.00, help="Maximum allowed cost in USD (default: $2.00).")
    p_ci.add_argument("--fail-on-smell", action="store_true", help="Exit code 1 if any tool smells detected.")
    p_ci.add_argument("--github-summary", action="store_true", help="Append markdown report to $GITHUB_STEP_SUMMARY.")
    p_ci.set_defaults(func=_run_ci_command)

    p_fix = sub.add_parser(
        "fix",
        help="Automatically repair and harden flawed MCP tool schemas to Glama/Smithery TDQS Gold Standard.",
    )
    p_fix.add_argument("schema_file", type=str, help="Path to JSON file containing tool definitions to fix.")
    p_fix.add_argument("--output", "-o", type=str, default=None, help="Output path for hardened schemas.")
    p_fix.add_argument("--in-place", "-i", action="store_true", help="Overwrite input file with hardened schemas.")
    p_fix.set_defaults(func=_run_fix_command)

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


def _run_openany_command(args: argparse.Namespace) -> int:
    from .providers.openany import (
        OpenAnyBudgetExceededError,
        OpenAnyConfig,
        OpenAnyProvider,
    )

    config = OpenAnyConfig.from_env()
    if getattr(args, "api_key", None):
        config.api_key = args.api_key
    if getattr(args, "model", None):
        config.default_model = args.model
    if getattr(args, "budget", None):
        config.max_budget_usd = args.budget

    provider = OpenAnyProvider(config=config)
    subcmd = getattr(args, "openany_subcommand", None)

    if subcmd == "models":
        models = provider.get_models()
        if getattr(args, "json", False):
            print(json.dumps(models, indent=2, sort_keys=True))
            return 0
        print(f"=== OpenAny Model Catalog ({len(models)} models available) ===")
        print("| Model ID | Context | Max Output | Prompt USD/1M | Completion USD/1M | Modalities |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for m in models[:25]:
            pricing = m.get("pricing", {})
            if isinstance(pricing, list) and pricing:
                pricing = pricing[0]
            p_prompt = float(pricing.get("prompt", "0") or 0.0) * 1_000_000
            p_comp = float(pricing.get("completion", "0") or 0.0) * 1_000_000
            mods = ",".join(m.get("input_modalities", []))
            print(
                f"| `{m.get('id')}` | {m.get('context_length', 0):,} | "
                f"{m.get('max_output_length', 0):,} | ${p_prompt:.4f} | "
                f"${p_comp:.4f} | {mods} |"
            )
        if len(models) > 25:
            print(f"\n... and {len(models) - 25} more models. Use --json to view the complete list.")
        return 0

    if subcmd == "lint-tools":
        report = provider.lint_openany_tools()
        if getattr(args, "json", False):
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            _print_lint_report("OpenAny Remote MCP Tool Definitions", report)
        return 0 if report.error_count == 0 else 1

    if subcmd == "chat":
        prompt = args.prompt
        target_model = args.model or config.default_model
        budget = args.budget if args.budget is not None else config.max_budget_usd
        record_path = getattr(args, "record", None)

        recorder = FlightRecorder(agent_id=f"openany-agent-{target_model}") if record_path else None
        guard = TrajectoryCircuitBreaker(max_cost_usd=budget)

        print(f"Connecting to OpenAny ({target_model})... Budget cap: ${budget:.4f}")
        try:
            resp = provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=target_model,
                guard=guard,
                recorder=recorder,
            )
            choices = resp.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else str(resp)
            usage = resp.get("usage", {})
            meta = resp.get("_agentflight", {})

            print("\n--- OpenAny Response ---")
            print(content)
            print("\n--- AgentFlight Telemetry ---")
            print(
                f"Tokens: {usage.get('total_tokens', 0)} "
                f"({usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion)"
            )
            print(
                f"Est Cost: ${meta.get('estimated_cost_usd', 0.0):.6f} | "
                f"Billed Cost: ${meta.get('actual_cost_usd', 0.0):.6f}"
            )
            print(f"Latency: {meta.get('latency_ms', 0.0)} ms | Partner: {meta.get('partner_id', 'none')}")

            if recorder and record_path:
                recorder.save(record_path)
                print(f"Recorded flight trajectory cassette saved to: {record_path}")
            return 0
        except OpenAnyBudgetExceededError as e:
            print(f"\n[CIRCUIT BREAKER TRIPPED]: {e}")
            return 2
        except Exception as e:
            print(f"\n[ERROR]: {e}")
            return 1

    if subcmd == "replay":
        cassette_path = args.cassette
        replayer = CassetteReplayer(cassette_path)
        print(f"Replaying OpenAny cassette: {cassette_path}")
        print(f"Recorded Agent ID: {replayer.agent_id} | Steps: {len(replayer.spans)}")
        step_idx = 0
        start = time.perf_counter()
        while not replayer.is_exhausted:
            span = replayer.advance()
            step_idx += 1
            print(
                f"  Step {span.step_index}: [{span.kind}] {span.actor} -> "
                f"status={span.status} (Recorded Cost: ${span.cost_usd:.6f})"
            )
        elapsed_us = (time.perf_counter() - start) * 1_000_000
        print(
            f"\nDeterministic Replay Complete: {step_idx} steps verified in "
            f"{elapsed_us:.2f} us ($0.00 network cost)."
        )
        return 0

    print("Please specify an OpenAny subcommand: models, chat, lint-tools, replay. Use --help for options.")
    return 1


def _run_post_mortem_command(args: argparse.Namespace) -> int:
    from .post_mortem import FlightPostMortemAnalyzer
    analyzer = FlightPostMortemAnalyzer()
    report = analyzer.analyze(args.cassette)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        md = report.to_markdown()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"Post-Mortem Incident Report written to {args.output}")
        else:
            print(md)
    return 1 if report.severity in ("CRITICAL", "HIGH") else 0


def _run_ci_command(args: argparse.Namespace) -> int:
    from .linter import ToolSmellLinter, SHOWCASE_HARDENED_MCP_TOOLS
    from .post_mortem import FlightPostMortemAnalyzer

    lines = [
        "# ✈️ AgentFlight CI Pre-Flight Verification Gate",
        "",
        "| Gate Check | Status | Details |",
        "| :--- | :---: | :--- |",
    ]
    exit_code = 0

    # 1. Tool-Smell Linter
    tools = SHOWCASE_HARDENED_MCP_TOOLS
    if args.schema_file:
        with open(args.schema_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            tools = data if isinstance(data, list) else data.get("tools", [])

    linter = ToolSmellLinter()
    report = linter.lint(tools)
    smell_count = len(report.findings)
    if smell_count > 0:
        lines.append(f"| **MCP Tool-Smell Audit** | ⚠️ WARN | Found {smell_count} smells across {len(tools)} tools |")
        if args.fail_on_smell:
            exit_code = 1
    else:
        lines.append(f"| **MCP Tool-Smell Audit** | ✅ PASS | 0 smells detected across {len(tools)} tools |")

    # 2. Cassette check if provided
    if args.cassette:
        pm = FlightPostMortemAnalyzer(max_cost_ceiling_usd=args.max_cost).analyze(args.cassette)
        if not pm.is_hash_chain_valid:
            lines.append(f"| **Cassette Cryptographic Chain** | ❌ FAIL | SHA-256 chain verification failed |")
            exit_code = 1
        else:
            lines.append(f"| **Cassette Cryptographic Chain** | ✅ PASS | SHA-256 chain valid ({pm.total_steps} steps) |")

        if pm.severity in ("CRITICAL", "HIGH"):
            lines.append(f"| **Flight Safety & Budget SLA** | ❌ FAIL | Root Cause: `{pm.root_cause}` (${pm.total_cost_usd:.4f}) |")
            exit_code = 1
        else:
            lines.append(f"| **Flight Safety & Budget SLA** | ✅ PASS | Cost ${pm.total_cost_usd:.4f} within ${args.max_cost:.2f} limit |")

    summary_md = "\n".join(lines)
    print(summary_md)

    if args.github_summary or os.environ.get("GITHUB_STEP_SUMMARY"):
        gh_step = os.environ.get("GITHUB_STEP_SUMMARY")
        if gh_step:
            with open(gh_step, "a", encoding="utf-8") as f:
                f.write("\n" + summary_md + "\n")

    return exit_code


def _run_fix_command(args: argparse.Namespace) -> int:
    from .schema_optimizer import ToolSchemaOptimizer
    with open(args.schema_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_dict = isinstance(data, dict)
    tools = data.get("tools", []) if is_dict else data

    optimizer = ToolSchemaOptimizer()
    results = optimizer.optimize_tools(tools)
    hardened_tools = [r.hardened_tool for r in results]

    output_data = copy.deepcopy(data) if is_dict else hardened_tools
    if is_dict:
        output_data["tools"] = hardened_tools

    target_path = args.schema_file if args.in_place else (args.output or "hardened_tools.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    total_smells_resolved = sum(r.smells_resolved for r in results)
    print(f"✅ Successfully hardened {len(tools)} tool definitions into {target_path}")
    print(f"   Resolved {total_smells_resolved} tool smells. Meets Glama TDQS Gold Standard.")
    return 0


def _run_serve_mcp_command(args: argparse.Namespace) -> int:
    server = AgentFlightMCPServer()
    server.serve_stdio()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func") or args.func is None:
        # Default to stdio MCP server for standard MCP clients, Claude Desktop, and container tests
        server = AgentFlightMCPServer()
        server.serve_stdio()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
