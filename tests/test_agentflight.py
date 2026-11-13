from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from agentflight import (
    GENESIS_HASH,
    RULE_CATALOG,
    SHOWCASE_FLAWED_MCP_TOOLS,
    SHOWCASE_HARDENED_MCP_TOOLS,
    CassetteReplayer,
    CassetteTamperError,
    CircuitBreakerTripped,
    FlightRecorder,
    ToolSmellLinter,
    TrajectoryCircuitBreaker,
    TrajectoryDivergenceError,
    canonical_hash,
    canonical_json,
    diff_trajectories,
    verify_cassette,
)
from agentflight.cli import main as cli_main

# ============================================================================
# 1. Recorder & SHA-256 Cassette Integrity Tests
# ============================================================================


def _make_sample_recorder() -> FlightRecorder:
    rec = FlightRecorder(agent_id="test-agent", metadata={"suite": "unit"})
    rec.record(
        kind="llm_turn",
        actor="gpt-4.1",
        input_payload={"messages": [{"role": "user", "content": "Check server health"}]},
        output_payload={"tool_call": "ping_host"},
        latency_ms=110.5,
        prompt_tokens=120,
        completion_tokens=25,
        cost_usd=0.0012,
    )
    rec.record(
        kind="tool_call",
        actor="ping_host",
        input_payload={"host": "10.0.0.1", "timeout_s": 2},
        output_payload={"alive": True, "rtt_ms": 1.4},
        latency_ms=4.2,
    )
    rec.record(
        kind="mcp_rpc",
        actor="pagerduty.ack_incident",
        input_payload={"incident_id": "INC-101"},
        output_payload={"acknowledged": True},
        latency_ms=45.0,
    )
    return rec


def test_canonical_json_key_ordering_invariance() -> None:
    payload_a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    payload_b = {"nested": {"y": 8, "z": 9}, "a": 1, "b": 2}
    assert canonical_json(payload_a) == canonical_json(payload_b)
    assert canonical_hash(payload_a) == canonical_hash(payload_b)


def test_flight_recorder_sha256_hash_chain() -> None:
    rec = _make_sample_recorder()
    assert len(rec.spans) == 3
    assert rec.spans[0].prev_hash == GENESIS_HASH
    assert rec.spans[1].prev_hash == rec.spans[0].step_hash
    assert rec.spans[2].prev_hash == rec.spans[1].step_hash
    assert rec.head_hash == rec.spans[2].step_hash
    assert verify_cassette(rec) is True


def test_flight_recorder_totals() -> None:
    rec = _make_sample_recorder()
    assert rec.total_tokens == 145
    assert rec.total_cost_usd == pytest.approx(0.0012)
    assert rec.total_latency_ms == pytest.approx(159.7)


def test_save_and_load_json_cassette(tmp_path: Path) -> None:
    rec = _make_sample_recorder()
    path = tmp_path / "sample.flight.json"
    rec.save(path)
    loaded = FlightRecorder.load(path, verify=True)
    assert loaded.agent_id == "test-agent"
    assert loaded.head_hash == rec.head_hash
    assert len(loaded.spans) == 3


def test_save_and_load_jsonl_cassette(tmp_path: Path) -> None:
    rec = _make_sample_recorder()
    path = tmp_path / "sample.flight.jsonl"
    rec.save(path)
    loaded = FlightRecorder.load(path, verify=True)
    assert loaded.agent_id == "test-agent"
    assert loaded.head_hash == rec.head_hash
    assert [s.actor for s in loaded.spans] == ["gpt-4.1", "ping_host", "pagerduty.ack_incident"]


def test_tamper_detection_output_payload_modified(tmp_path: Path) -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["spans"][1]["output_payload"]["alive"] = False
    with pytest.raises(CassetteTamperError, match="Tampered span content at step 1"):
        verify_cassette(cassette)


def test_tamper_detection_input_payload_modified() -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["spans"][0]["input_payload"]["messages"] = []
    with pytest.raises(CassetteTamperError, match="Tampered input_payload at step 0"):
        verify_cassette(cassette)


def test_tamper_detection_broken_prev_hash() -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["spans"][2]["prev_hash"] = "f" * 64
    with pytest.raises(CassetteTamperError, match="Broken prev_hash chain at step 2"):
        verify_cassette(cassette)


def test_tamper_detection_non_sequential_step_index() -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["spans"][1]["step_index"] = 99
    with pytest.raises(CassetteTamperError, match="Non-sequential step_index"):
        verify_cassette(cassette)


def test_tamper_detection_step_count_mismatch() -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["step_count"] = 10
    with pytest.raises(CassetteTamperError, match="Step count mismatch"):
        verify_cassette(cassette)


def test_tamper_detection_head_hash_mismatch() -> None:
    rec = _make_sample_recorder()
    cassette = rec.to_cassette_dict()
    cassette["head_hash"] = "a" * 64
    with pytest.raises(CassetteTamperError, match="Cassette head_hash mismatch"):
        verify_cassette(cassette)


def test_wrap_tool_records_success_and_exception() -> None:
    rec = FlightRecorder(agent_id="wrapper-test")

    def add_numbers(x: int, y: int) -> Dict[str, Any]:
        return {"sum": x + y}

    def failing_tool(query: str) -> Dict[str, Any]:
        raise RuntimeError("Database connection refused")

    wrapped_ok = rec.wrap_tool("math.add", add_numbers)
    wrapped_err = rec.wrap_tool("db.query", failing_tool)

    res = wrapped_ok(x=7, y=5)
    assert res == {"sum": 12}

    with pytest.raises(RuntimeError, match="Database connection refused"):
        wrapped_err(query="SELECT 1")

    assert len(rec.spans) == 2
    assert rec.spans[0].status == "ok"
    assert rec.spans[1].status == "error"
    assert rec.spans[1].output_payload["error_type"] == "RuntimeError"


# ============================================================================
# 2. Deterministic Cassette Replay & Divergence Tests
# ============================================================================


def test_strict_cassette_replay_success() -> None:
    rec = _make_sample_recorder()
    replayer = CassetteReplayer(rec, strict_order=True)
    assert replayer.remaining_steps == 3

    out0 = replayer.replay_step(
        "llm_turn",
        "gpt-4.1",
        {"messages": [{"role": "user", "content": "Check server health"}]},
    )
    assert out0 == {"tool_call": "ping_host"}

    ping_stub = replayer.stub_tool("ping_host", kind="tool_call")
    out1 = ping_stub(timeout_s=2, host="10.0.0.1")  # Reordered kwargs still match canonical hash!
    assert out1 == {"alive": True, "rtt_ms": 1.4}

    out2 = replayer.replay_step("mcp_rpc", "pagerduty.ack_incident", {"incident_id": "INC-101"})
    assert out2 == {"acknowledged": True}
    assert replayer.remaining_steps == 0
    assert replayer.tokens_saved == 145
    assert replayer.cost_saved_usd == pytest.approx(0.0012)


def test_strict_replay_divergence_structural_diff() -> None:
    rec = _make_sample_recorder()
    replayer = CassetteReplayer(rec, strict_order=True)
    replayer.replay_step(
        "llm_turn",
        "gpt-4.1",
        {"messages": [{"role": "user", "content": "Check server health"}]},
    )
    with pytest.raises(TrajectoryDivergenceError) as exc_info:
        replayer.replay_step(
            "tool_call",
            "ping_host",
            {"host": "10.0.0.99", "extra_flag": True},
        )
    err = exc_info.value
    assert err.step_index == 1
    assert err.diff["missing_keys"] == ["timeout_s"]
    assert err.diff["extra_keys"] == ["extra_flag"]
    assert err.diff["changed_values"]["host"] == {"expected": "10.0.0.1", "actual": "10.0.0.99"}


def test_strict_replay_exceeding_cassette_length() -> None:
    rec = _make_sample_recorder()
    replayer = CassetteReplayer(rec, strict_order=True)
    for sp in rec.spans:
        replayer.replay_step(sp.kind, sp.actor, sp.input_payload)
    with pytest.raises(TrajectoryDivergenceError, match="exceeded recorded cassette length"):
        replayer.replay_step("tool_call", "ping_host", {"host": "10.0.0.1", "timeout_s": 2})


def test_unordered_cassette_replay_and_reset() -> None:
    rec = _make_sample_recorder()
    replayer = CassetteReplayer(rec, strict_order=False)
    # Call step 2 before step 1
    out2 = replayer.replay_step("mcp_rpc", "pagerduty.ack_incident", {"incident_id": "INC-101"})
    assert out2 == {"acknowledged": True}
    out1 = replayer.replay_step("tool_call", "ping_host", {"host": "10.0.0.1", "timeout_s": 2})
    assert out1["alive"] is True

    replayer.reset()
    assert replayer.cursor == 0


def test_unordered_replay_missing_call_raises_divergence() -> None:
    rec = _make_sample_recorder()
    replayer = CassetteReplayer(rec, strict_order=False)
    with pytest.raises(TrajectoryDivergenceError, match="No recorded cassette span matches"):
        replayer.replay_step("tool_call", "ping_host", {"host": "unknown", "timeout_s": 99})


# ============================================================================
# 3. MCP Tool-Smell Linter Tests (All 10 Rules TS001 - TS010)
# ============================================================================


def test_rule_catalog_has_all_10_rules() -> None:
    expected = {f"TS{i:03d}" for i in range(1, 11)}
    assert set(RULE_CATALOG.keys()) == expected


def test_ts001_missing_or_short_tool_description() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "get_weather",
                "description": "Too short",
                "inputSchema": {"type": "object", "required": [], "properties": {}},
            }
        ]
    )
    assert "TS001" in report.rule_counts


def test_ts002_property_missing_description() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "query_logs",
                "description": "Query application logs across Kubernetes pods by namespace.",
                "inputSchema": {
                    "type": "object",
                    "required": ["namespace"],
                    "properties": {"namespace": {"type": "string"}},
                },
            }
        ]
    )
    assert "TS002" in report.rule_counts
    assert any(f.property_path == "properties.namespace" for f in report.findings)


def test_ts003_deeply_nested_schema() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "complex_query",
                "description": "Execute a structured multi-stage analytics aggregation query.",
                "inputSchema": {
                    "type": "object",
                    "required": ["a"],
                    "properties": {
                        "a": {
                            "type": "object",
                            "description": "Level 1",
                            "properties": {
                                "b": {
                                    "type": "object",
                                    "description": "Level 2",
                                    "properties": {
                                        "c": {
                                            "type": "object",
                                            "description": "Level 3",
                                            "properties": {
                                                "d": {"type": "string", "description": "Level 4"}
                                            },
                                        }
                                    },
                                }
                            },
                        }
                    },
                },
            }
        ]
    )
    assert "TS003" in report.rule_counts


def test_ts004_excessive_parameter_count() -> None:
    linter = ToolSmellLinter()
    props = {f"param_{i}": {"type": "string", "description": f"Param {i}"} for i in range(10)}
    report = linter.lint(
        [
            {
                "name": "omni_tool",
                "description": "Perform an operation with far too many top-level parameters.",
                "inputSchema": {"type": "object", "required": ["param_0"], "properties": props},
            }
        ]
    )
    assert "TS004" in report.rule_counts


def test_ts005_ambiguous_boolean_flag_name() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "list_tickets",
                "description": "List customer support tickets from the helpdesk queue.",
                "inputSchema": {
                    "type": "object",
                    "required": ["flag"],
                    "properties": {
                        "flag": {"type": "boolean", "description": "Whether to filter something."}
                    },
                },
            }
        ]
    )
    assert "TS005" in report.rule_counts


def test_ts006_unconstrained_finite_set_string() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "list_deployments",
                "description": "List recent service deployments filtered by lifecycle status.",
                "inputSchema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string", "description": "Deployment status."}
                    },
                },
            }
        ]
    )
    assert "TS006" in report.rule_counts


def test_ts007_missing_required_array() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "fetch_order",
                "description": "Fetch e-commerce order details by unique order identifier.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Unique order ID."}
                    },
                },
            }
        ]
    )
    assert "TS007" in report.rule_counts


def test_ts008_high_lexical_overlap_between_tools() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "search_user_profiles",
                "description": "Search user profiles in the identity database by email or name.",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string", "description": "Search query."}},
                },
            },
            {
                "name": "find_user_profiles",
                "description": "Search user profiles in the identity database by name or email.",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string", "description": "Search query."}},
                },
            },
        ]
    )
    assert "TS008" in report.rule_counts


def test_ts009_bloated_schema_token_footprint() -> None:
    linter = ToolSmellLinter()
    huge_desc = "Detailed parameter documentation. " * 60
    report = linter.lint(
        [
            {
                "name": "bloated_tool",
                "description": huge_desc,
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": huge_desc},
                    },
                },
            }
        ]
    )
    assert "TS009" in report.rule_counts


def test_ts010_destructive_tool_missing_safety_guard() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "drop_database_table",
                "description": "Drops a SQL table from the primary production database.",
                "inputSchema": {
                    "type": "object",
                    "required": ["table_name"],
                    "properties": {
                        "table_name": {"type": "string", "description": "Target SQL table name."}
                    },
                },
            }
        ]
    )
    assert "TS010" in report.rule_counts


def test_hardened_showcase_suite_scores_100() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(SHOWCASE_HARDENED_MCP_TOOLS)
    assert report.ergonomics_score == 100
    assert report.grade == "A"
    assert len(report.findings) == 0


def test_flawed_showcase_suite_triggers_multiple_rules() -> None:
    linter = ToolSmellLinter()
    report = linter.lint(SHOWCASE_FLAWED_MCP_TOOLS)
    assert report.ergonomics_score < 50
    assert report.error_count >= 3
    for rule_id in ("TS001", "TS002", "TS003", "TS004", "TS005", "TS006", "TS007", "TS008", "TS010"):
        assert rule_id in report.rule_counts


def test_openai_function_schema_normalization() -> None:
    linter = ToolSmellLinter()
    openai_tool = {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Retrieve the latest real-time equity trade price by ticker symbol.",
            "parameters": {
                "type": "object",
                "required": ["ticker"],
                "properties": {
                    "ticker": {"type": "string", "description": "NYSE/NASDAQ ticker symbol."}
                },
            },
        },
    }
    report = linter.lint([openai_tool])
    assert report.ergonomics_score == 100


# ============================================================================
# 4. Real-Time Circuit Breaker Guard Tests
# ============================================================================


def test_circuit_breaker_exact_call_loop() -> None:
    breaker = TrajectoryCircuitBreaker(max_identical_repeats=3)
    breaker.observe("read_file", {"path": "/etc/hosts"})
    breaker.observe("read_file", {"path": "/etc/hosts"})
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("read_file", {"path": "/etc/hosts"})
    assert exc_info.value.reason == "exact_call_loop"
    assert exc_info.value.step_index == 2


def test_circuit_breaker_ping_pong_2_cycle() -> None:
    breaker = TrajectoryCircuitBreaker(max_ping_pong_cycles=2)
    breaker.observe("tool_a", {"x": 1})
    breaker.observe("tool_b", {"y": 2})
    breaker.observe("tool_a", {"x": 1})
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("tool_b", {"y": 2})
    assert exc_info.value.reason == "ping_pong_oscillation"
    assert exc_info.value.evidence["period"] == 2


def test_circuit_breaker_ping_pong_3_cycle() -> None:
    breaker = TrajectoryCircuitBreaker(max_ping_pong_cycles=2)
    cycle = [("step_a", {"v": 1}), ("step_b", {"v": 2}), ("step_c", {"v": 3})]
    for actor, payload in cycle:
        breaker.observe(actor, payload)
    breaker.observe("step_a", {"v": 1})
    breaker.observe("step_b", {"v": 2})
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("step_c", {"v": 3})
    assert exc_info.value.reason == "ping_pong_oscillation"
    assert exc_info.value.evidence["period"] == 3


def test_circuit_breaker_consecutive_error_storm() -> None:
    breaker = TrajectoryCircuitBreaker(max_consecutive_errors=3)
    breaker.observe("sql_query", {"q": "1"}, status="error")
    breaker.observe("sql_query", {"q": "2"}, status="error")
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("sql_query", {"q": "3"}, status="error")
    assert exc_info.value.reason == "consecutive_error_storm"


def test_circuit_breaker_error_counter_resets_on_ok_step() -> None:
    breaker = TrajectoryCircuitBreaker(max_consecutive_errors=3)
    breaker.observe("sql_query", {"q": "1"}, status="error")
    breaker.observe("sql_query", {"q": "2"}, status="error")
    breaker.observe("sql_query", {"q": "3"}, status="ok")
    assert breaker.stats.consecutive_errors == 0
    breaker.observe("sql_query", {"q": "4"}, status="error")
    assert breaker.stats.consecutive_errors == 1


def test_circuit_breaker_token_budget_exceeded() -> None:
    breaker = TrajectoryCircuitBreaker(max_total_tokens=1000)
    breaker.observe("llm", {"p": 1}, prompt_tokens=500, completion_tokens=300)
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("llm", {"p": 2}, prompt_tokens=200, completion_tokens=100)
    assert exc_info.value.reason == "token_budget_exceeded"


def test_circuit_breaker_cost_budget_exceeded() -> None:
    breaker = TrajectoryCircuitBreaker(max_cost_usd=0.05)
    breaker.observe("llm", {"p": 1}, cost_usd=0.03)
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        breaker.observe("llm", {"p": 2}, cost_usd=0.03)
    assert exc_info.value.reason == "cost_budget_exceeded"


def test_circuit_breaker_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="max_identical_repeats"):
        TrajectoryCircuitBreaker(max_identical_repeats=1)
    with pytest.raises(ValueError, match="max_ping_pong_cycles"):
        TrajectoryCircuitBreaker(max_ping_pong_cycles=1)
    with pytest.raises(ValueError, match="max_consecutive_errors"):
        TrajectoryCircuitBreaker(max_consecutive_errors=0)


# ============================================================================
# 5. Trajectory Evaluator & Diff Engine Tests
# ============================================================================


def test_trajectory_diff_identical_trajectories() -> None:
    rec = _make_sample_recorder()
    report = diff_trajectories(rec, rec)
    assert report.tool_precision == 1.0
    assert report.tool_recall == 1.0
    assert report.tool_f1 == 1.0
    assert report.argument_exact_match_rate == 1.0
    assert report.step_efficiency_ratio == 1.0
    assert report.token_delta == 0
    assert report.cost_delta_usd == 0.0
    assert report.goal_completion_score == 1.0
    assert report.passed is True


def test_trajectory_diff_divergent_candidate() -> None:
    golden = _make_sample_recorder()
    candidate = FlightRecorder(agent_id="divergent")
    candidate.record(
        kind="llm_turn",
        actor="gpt-4.1",
        input_payload={"messages": [{"role": "user", "content": "Check server health"}]},
        output_payload={"tool_call": "ping_host"},
        prompt_tokens=200,
        completion_tokens=50,
        cost_usd=0.0050,
    )
    candidate.record(
        kind="tool_call",
        actor="ping_host",
        input_payload={"host": "10.0.0.99", "timeout_s": 2},  # Wrong host argument
        output_payload={"alive": False},
    )
    candidate.record(
        kind="tool_call",
        actor="wrong_tool",
        input_payload={},
        output_payload={"ok": False},
        status="error",
    )

    report = diff_trajectories(golden, candidate)
    assert report.tool_precision == pytest.approx(0.5)
    assert report.tool_recall == pytest.approx(0.5)
    assert report.argument_exact_match_rate == 0.0
    assert report.token_delta == 105
    assert report.passed is False
    statuses = [d.status for d in report.step_diffs]
    assert statuses == ["exact_match", "arg_mismatch", "actor_mismatch"]


def test_trajectory_diff_extra_and_missing_steps() -> None:
    golden = _make_sample_recorder()
    short_candidate = FlightRecorder(agent_id="short")
    short_candidate.record(
        kind="llm_turn",
        actor="gpt-4.1",
        input_payload={"messages": [{"role": "user", "content": "Check server health"}]},
        output_payload={"tool_call": "ping_host"},
    )
    report = diff_trajectories(golden, short_candidate)
    assert any(d.status == "missing_step" for d in report.step_diffs)


# ============================================================================
# 6. CLI & Benchmark Suite Tests
# ============================================================================


def test_cli_lint_showcase(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["lint"])
    captured = capsys.readouterr().out
    assert code == 0
    assert "Showcase Flawed MCP Tool Suite" in captured
    assert "Showcase Hardened MCP Tool Suite" in captured


def test_cli_lint_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["lint", "--json"])
    captured = capsys.readouterr().out
    assert code == 0
    parsed = json.loads(captured)
    assert parsed["hardened_suite"]["ergonomics_score"] == 100


def test_cli_lint_custom_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "tools.json"
    schema_path.write_text(json.dumps(SHOWCASE_HARDENED_MCP_TOOLS), encoding="utf-8")
    code = cli_main(["lint", "--schema-file", str(schema_path)])
    assert code == 0


def test_cli_demo_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["demo"])
    captured = capsys.readouterr().out
    assert code == 0
    assert "[1/4] Recorded & Verified Golden Cassette" in captured
    assert "[2/4] Deterministic Cassette Replay" in captured
    assert "[3/4] Circuit Breaker Guard: Tripped=True" in captured
    assert "[4/4] Golden Trajectory Diff" in captured


def test_cli_benchmark_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["benchmark"])
    captured = capsys.readouterr().out
    assert code == 0
    assert "FlightRecorder.record" in captured
    assert "ToolSmellLinter.lint" in captured


def test_cli_benchmark_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli_main(["benchmark", "--json"])
    captured = capsys.readouterr().out
    assert code == 0
    metrics = json.loads(captured)
    assert metrics["replay_1000_spans_ms"] < 250.0
    assert metrics["lint_200_findings"] > 0


# ============================================================================
# 7. Parametrized Rule Verification Tests (Ensuring 55+ Total Tests)
# ============================================================================


@pytest.mark.parametrize(
    "bad_bool_name",
    ["flag", "mode", "option", "data", "value", "switch", "toggle", "bool"],
)
def test_parametrized_ts005_ambiguous_booleans(bad_bool_name: str) -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "update_setting",
                "description": "Update an application configuration setting by key.",
                "inputSchema": {
                    "type": "object",
                    "required": [bad_bool_name],
                    "properties": {
                        bad_bool_name: {"type": "boolean", "description": "Boolean switch."}
                    },
                },
            }
        ]
    )
    assert "TS005" in report.rule_counts


@pytest.mark.parametrize(
    "finite_name",
    ["status", "sort", "order", "format", "env", "role", "type", "severity", "priority"],
)
def test_parametrized_ts006_finite_strings(finite_name: str) -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "filter_events",
                "description": "Filter security audit log events across the organization.",
                "inputSchema": {
                    "type": "object",
                    "required": [finite_name],
                    "properties": {
                        finite_name: {"type": "string", "description": "Filter value."}
                    },
                },
            }
        ]
    )
    assert "TS006" in report.rule_counts


@pytest.mark.parametrize(
    "destructive_prefix",
    ["delete_", "drop_", "remove_", "transfer_", "exec_", "destroy_", "purge_", "truncate_"],
)
def test_parametrized_ts010_destructive_prefixes(destructive_prefix: str) -> None:
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": f"{destructive_prefix}production_entity",
                "description": "Mutates the target production entity in the cluster.",
                "inputSchema": {
                    "type": "object",
                    "required": ["entity_id"],
                    "properties": {
                        "entity_id": {"type": "string", "description": "Target entity ID."}
                    },
                },
            }
        ]
    )
    assert "TS010" in report.rule_counts


def test_linter_resolves_defs_ref_for_property_description_and_enum() -> None:
    """Verify that $ref pointers to $defs resolve descriptions and enum constraints."""
    linter = ToolSmellLinter()
    report = linter.lint(
        [
            {
                "name": "update_agent_status",
                "description": "Updates the lifecycle state of a managed autonomous agent.",
                "inputSchema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"$ref": "#/$defs/AgentLifecycleStatus"}
                    },
                    "$defs": {
                        "AgentLifecycleStatus": {
                            "type": "string",
                            "description": "Canonical lifecycle status of the agent.",
                            "enum": ["active", "paused", "terminated"]
                        }
                    }
                },
            }
        ]
    )
    # TS002 (missing description) should NOT be flagged because $ref target provides description
    assert "TS002" not in report.rule_counts
    # TS006 (unconstrained finite string) should NOT be flagged because $ref target has enum
    assert "TS006" not in report.rule_counts
    assert report.ergonomics_score >= 95


def test_linter_computes_depth_through_defs_ref() -> None:
    """Verify that $ref nesting depth is correctly traversed and bounded."""
    linter = ToolSmellLinter(max_schema_depth=2)
    report = linter.lint(
        [
            {
                "name": "deep_nested_tool",
                "description": "Processes deeply nested tree structured payloads.",
                "inputSchema": {
                    "type": "object",
                    "required": ["root"],
                    "properties": {
                        "root": {"$ref": "#/definitions/NodeLevel1"}
                    },
                    "definitions": {
                        "NodeLevel1": {
                            "type": "object",
                            "properties": {
                                "child": {
                                    "type": "object",
                                    "properties": {
                                        "leaf": {"type": "string", "description": "Leaf value."}
                                    }
                                }
                            }
                        }
                    }
                },
            }
        ]
    )
    assert "TS003" in report.rule_counts

