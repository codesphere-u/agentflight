"""
Comprehensive tests for AgentFlight v1.6.0 capabilities:
- Runtime Policy Firewall (`agentflight.policy`)
- Behavioral Trajectory Contracts & Assertions (`agentflight.assertions`)
- Time-Travel Cassette Forking & Counterfactual Patching (`FlightRecorder.fork_from` / `CassetteReplayer.fork_at`)
- 8-Tool MCP Server & Hosted Security Isolation (`agentflight.mcp_server` + `api.index`)
- CLI `replay`, `policy-audit`, `contract`, `ci --contract --policy-mode`, and `doctor`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentflight import (
    MCP_TOOLS,
    CassetteReplayer,
    FlightContract,
    FlightRecorder,
    FlightSession,
    PolicyViolationError,
    ToolSmellLinter,
    TrajectoryCircuitBreaker,
    TrajectoryPolicyEngine,
    assert_trajectory,
    compare_cassettes,
    verify_cassette,
)
from agentflight.cli import main as cli_main
from agentflight.mcp_server import AgentFlightMCPServer


def _build_sample_recorder() -> FlightRecorder:
    rec = FlightRecorder(agent_id="sre-planner-v1", redact_secrets=True)
    rec.record("llm_turn", "planner", {"goal": "diagnose latency"}, {"plan": ["metrics", "logs"]}, latency_ms=120.0, prompt_tokens=150, completion_tokens=40, cost_usd=0.002)
    rec.record("tool_call", "query_metrics", {"service": "checkout"}, {"p99_ms": 920}, latency_ms=45.0, cost_usd=0.0005)
    rec.record("tool_call", "fetch_logs", {"service": "checkout", "limit": 20}, {"errors": ["timeout"]}, latency_ms=55.0, cost_usd=0.0005)
    rec.record("llm_turn", "summarizer", {"context": "timeout"}, {"summary": "db pool exhausted"}, latency_ms=90.0, prompt_tokens=200, completion_tokens=50, cost_usd=0.0025)
    return rec


def test_policy_firewall_blocks_ssrf_traversal_sql_secrets_and_mutations() -> None:
    fw = TrajectoryPolicyEngine(mode="strict", blocked_actors=["raw_shell"], max_mutations=1)

    assert fw.evaluate("raw_shell", {"cmd": "ls"}).violations[0].rule_id == "PF001"

    ssrf = fw.evaluate("http_fetch", {"url": "http://169.254.169.254/latest/meta-data/iam"})
    assert not ssrf.allowed
    assert ssrf.violations[0].rule_id == "PF003"

    # Semver strings should NOT trigger SSRF false positives
    clean_ver = fw.evaluate("release_check", {"version": "v10.0.0.1", "tag": "1.6.0"})
    assert clean_ver.allowed
    assert not clean_ver.violations

    traversal = fw.evaluate("read_file", {"path": "../../../etc/passwd"})
    assert not traversal.allowed
    assert traversal.violations[0].rule_id == "PF004"

    sql = fw.evaluate("run_query", {"sql": "DROP TABLE users;"})
    assert not sql.allowed
    assert sql.violations[0].rule_id == "PF005"

    leak = fw.evaluate("webhook_post", {"headers": {"Authorization": "Bearer sk-proj-supersecretkey123456"}})
    assert not leak.allowed
    assert leak.violations[0].rule_id == "PF006"

    # Mutation cap: 1st allowed with strict warn, 2nd triggers PF007 block
    m1 = fw.evaluate("update_ticket", {"id": 10})
    assert m1.allowed
    assert m1.action == "warn"
    m2 = fw.evaluate("delete_ticket", {"id": 10})
    assert not m2.allowed
    assert any(v.rule_id == "PF007" for v in m2.violations)

    # Read-only blocks any mutation immediately
    ro = TrajectoryPolicyEngine(mode="read-only")
    with pytest.raises(PolicyViolationError) as exc_info:
        ro.evaluate("write_config", {"k": "v"}, raise_on_block=True)
    assert exc_info.value.rule_id == "PF002"


def test_policy_custom_rule_and_circuit_breaker_integration() -> None:
    fw = TrajectoryPolicyEngine(mode="standard")
    fw.add_rule(
        "CUSTOM_PROD",
        lambda actor, payload, kind: "Production deploys require ticket_id"
        if actor == "deploy_release" and not payload.get("ticket_id")
        else None,
        severity="block",
        description="Require change ticket before prod deploy",
    )

    guard = TrajectoryCircuitBreaker(max_cost_usd=1.0, policy=fw)
    guard.observe("query_metrics", {"service": "api"})
    with pytest.raises(PolicyViolationError) as exc_info:
        guard.observe("deploy_release", {"env": "prod"})
    assert exc_info.value.rule_id == "CUSTOM_PROD"

    guard.reset()
    assert fw.evaluate("deploy_release", {"env": "prod", "ticket_id": "CHG-42"}).allowed

    # Offline cassette audit
    rec = _build_sample_recorder()
    rec.record("tool_call", "run_query", {"sql": "TRUNCATE TABLE audit_log"}, {"ok": False}, status="error")
    audit = fw.audit_cassette(rec)
    assert not audit.passed
    assert audit.block_count == 1
    assert "PF005" in audit.to_markdown()


def test_behavioral_contract_assertions_and_session(tmp_path: Path) -> None:
    rec = _build_sample_recorder()
    cassette_path = tmp_path / "sample.flight.json"
    rec.save(cassette_path)

    contract = (
        FlightContract("sre-sla")
        .must_call("query_metrics", min_calls=1, max_calls=2)
        .must_not_call("drop_database")
        .must_follow_order(["planner", "query_metrics", "summarizer"])
        .max_steps(6)
        .max_cost_usd(0.05)
        .max_tokens(2000)
        .max_total_latency_ms(500.0)
        .max_step_latency_ms(200.0)
        .zero_errors()
        .require_valid_hash_chain(True)
        .require_no_secret_leaks(True)
    )

    report = assert_trajectory(cassette_path, contract)
    assert report.passed
    assert report.score == 100.0
    assert report.failed_rules == 0
    assert "PASS" in report.to_markdown()

    # Round-trip JSON file serialization
    contract_file = tmp_path / "contract.json"
    contract_file.write_text(json.dumps(contract.to_dict()), encoding="utf-8")
    loaded = FlightContract.from_file(contract_file)
    assert loaded.evaluate(cassette_path).passed

    # Failing assertion raises AssertionError with rule details
    bad_contract = FlightContract("strict-fail").must_not_call("query_metrics").max_steps(2)
    with pytest.raises(AssertionError, match="strict-fail"):
        assert_trajectory(rec, bad_contract)

    # FlightSession integration
    with FlightSession(tmp_path / "session.flight.json", mode="record") as sess:
        sess.record_step("tool_call", "query_metrics", {"q": 1}, {"ok": True}, cost_usd=0.001)
        rep = sess.assert_contract(FlightContract("sess").must_call("query_metrics").zero_errors())
        assert rep.passed


def test_time_travel_cassette_forking_and_counterfactual_diff(tmp_path: Path) -> None:
    baseline = _build_sample_recorder()
    replayer = CassetteReplayer(baseline)
    assert replayer.advance().actor == "planner"
    assert replayer.advance().actor == "query_metrics"

    # Fork right at cursor=2 (fetch_logs) with a counterfactual override showing healthy logs
    forked = replayer.fork_at(
        override_output={"errors": [], "cache_hit": True},
        override_status="ok",
    )
    assert verify_cassette(forked) is True
    assert len(forked.spans) == 3
    assert forked.metadata["forked_at_step"] == 2
    assert forked.metadata["forked_from_agent_id"] == baseline.agent_id
    assert forked.spans[2].output_payload["cache_hit"] is True

    forked.record("llm_turn", "summarizer", {"context": "healthy"}, {"summary": "no action needed"}, latency_ms=40.0, cost_usd=0.001)
    assert verify_cassette(forked) is True
    diff = compare_cassettes(baseline, forked)
    assert not diff.regression_detected
    assert diff.golden_steps == 4 and diff.candidate_steps == 4


def test_mcp_server_8_tools_lint_clean_and_hosted_isolation(tmp_path: Path) -> None:
    lint_report = ToolSmellLinter().lint(MCP_TOOLS)
    assert len(MCP_TOOLS) == 8
    assert lint_report.error_count == 0, f"MCP_TOOLS self-lint failed: {lint_report.to_dict()}"

    srv = AgentFlightMCPServer()
    rec = _build_sample_recorder()
    cassette_dict = rec.to_cassette_dict()

    # 1. optimize_tools
    opt_res = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "agentflight_optimize_tools",
                "arguments": {"tools": [{"name": "get_user", "description": "get", "inputSchema": {"properties": {"id": {}}}}]},
            },
        }
    )
    assert opt_res is not None
    opt_data = opt_res["result"]["structuredContent"]
    assert opt_data["tools_optimized"] == 1
    assert opt_data["post_lint_score"] >= 90

    # 2. post_mortem via inline cassette_json
    pm_res = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "agentflight_post_mortem", "arguments": {"cassette_json": cassette_dict}},
        }
    )
    assert pm_res is not None
    assert pm_res["result"]["structuredContent"]["severity"] == "CLEAN"

    # 3. audit_policy single call & inline cassette
    pol_res = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "agentflight_audit_policy",
                "arguments": {"mode": "strict", "actor": "http_get", "input_payload": {"url": "http://localhost:8000"}},
            },
        }
    )
    assert pol_res is not None
    assert pol_res["result"]["structuredContent"]["passed"] is False

    # 4. evaluate_contract via inline cassette
    c_res = srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "agentflight_evaluate_contract",
                "arguments": {
                    "cassette_json": cassette_dict,
                    "contract": {"name": "mcp-sla", "must_call": ["planner"], "max_cost_usd": 0.1},
                },
            },
        }
    )
    assert c_res is not None
    assert c_res["result"]["structuredContent"]["passed"] is True

    # Hosted FastAPI security check: exposes 5 stateless tools and blocks forbidden cassette_path arg
    import sys

    root_dir = str(Path(__file__).resolve().parent.parent)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from api.index import app

    client = TestClient(app)
    tools_list = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
    names = {t["name"] for t in tools_list}
    assert {
        "agentflight_lint_tools",
        "agentflight_optimize_tools",
        "agentflight_post_mortem",
        "agentflight_audit_policy",
        "agentflight_evaluate_contract",
    }.issubset(names)
    for t in tools_list:
        assert "cassette_path" not in t.get("inputSchema", {}).get("properties", {})

    blocked_arg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "agentflight_post_mortem", "arguments": {"cassette_path": "/etc/passwd"}},
        },
    ).json()
    assert blocked_arg["result"]["isError"] is True


def test_cli_v16_commands(tmp_path: Path, capsys: Any) -> None:
    rec = _build_sample_recorder()
    c_path = tmp_path / "v16.flight.json"
    rec.save(c_path)
    fork_path = tmp_path / "v16_fork.flight.json"
    contract_path = tmp_path / "sla.json"
    contract_path.write_text(
        json.dumps({"name": "cli-sla", "must_call": ["query_metrics"], "zero_errors": True, "max_cost_usd": 0.5}),
        encoding="utf-8",
    )

    assert cli_main(["replay", str(c_path), "--json"]) == 0
    assert cli_main(["replay", str(c_path), "--fork-at", "2", "--fork-out", str(fork_path), "--json"]) == 0
    assert fork_path.exists()
    assert verify_cassette(FlightRecorder.load(fork_path)) is True

    assert cli_main(["policy-audit", str(c_path), "--mode", "strict", "--json"]) == 0
    assert cli_main(["contract", str(c_path), "--contract", str(contract_path), "--json"]) == 0
    assert cli_main(["ci", "--cassette", str(c_path), "--contract", str(contract_path), "--policy-mode", "strict"]) == 0
    capsys.readouterr()
    assert cli_main(["doctor", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["healthy"] is True
    assert any(c["name"] == "policy_and_contracts" and c["ok"] for c in out["checks"])
