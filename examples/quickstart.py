"""End-to-end AgentFlight example: Lint an MCP tool schema, record an agent trajectory,
verify the cryptographic hash-chain cassette, replay in <0.02ms, and export OTel spans.

Run:  python examples/quickstart.py
Everything is offline and deterministic with $0.00 token spend.
"""

import tempfile
from pathlib import Path

from agentflight import (
    CassetteReplayer,
    FlightRecorder,
    ToolSmellLinter,
    export_cassette_to_otel,
    verify_cassette,
)


def main() -> dict:
    # 1. Pre-deployment static gate: Lint an MCP tool schema for anti-patterns
    flawed_tool = {
        "name": "delete_all_records",
        "description": "Deletes records from the database without confirmation",
        "parameters": {
            "type": "object",
            "properties": {
                "flag": {"type": "boolean"},  # TS003: Ambiguous boolean flag
                "mode": {"type": "string"},   # TS005: Unconstrained string without enum
            },
            "required": ["mode"],
        },
    }
    linter = ToolSmellLinter()
    report = linter.lint([flawed_tool])
    print(f"ToolSmellLinter: Ergonomics Score={report.ergonomics_score}/100, Grade={report.grade}, Findings={len(report.findings)}")
    assert len(report.findings) > 0, "Linter should detect tool smells in flawed schema"

    # 2. Flight recording: Capture agent trajectory into tamper-evident SHA-256 chain
    recorder = FlightRecorder(agent_id="agent_analyst_v1", metadata={"task_id": "task_summarize_sales_01"})
    recorder.record(
        kind="tool_call",
        actor="sql_query",
        input_payload={"query": "SELECT sum(amount) FROM sales WHERE month = '2026-10'"},
        output_payload={"total_minor": 15000000, "currency": "UGX"},
        prompt_tokens=100,
        completion_tokens=20,
        latency_ms=4.2,
    )
    recorder.record(
        kind="tool_call",
        actor="calculate_growth",
        input_payload={"current": 15000000, "previous": 12000000},
        output_payload={"growth_pct": 25.0},
        prompt_tokens=70,
        completion_tokens=15,
        latency_ms=1.1,
    )
    recorder.record(
        kind="tool_call",
        actor="format_report",
        input_payload={"headline": "October Sales Growth", "growth_pct": 25.0},
        output_payload={"status": "REPORT_READY", "summary": "Growth at +25.0% MoM"},
        prompt_tokens=110,
        completion_tokens=30,
        latency_ms=2.0,
    )

    # 3. Persist to disk and verify cryptographic cassette integrity
    with tempfile.TemporaryDirectory() as tmp:
        cassette_path = Path(tmp) / "october_sales.flight.json"
        recorder.save(cassette_path)
        loaded = FlightRecorder.load(cassette_path, verify=True)
        is_valid = verify_cassette(loaded)
        assert is_valid, "Cassette verification failed"
        print(f"FlightRecorder: 3 steps recorded, SHA-256 chain verified. Head={recorder.head_hash[:16]}...")

        # 4. CI Replay: Deterministically replay trajectory in <0.02ms with $0.00 spend
        replayer = CassetteReplayer(cassette_path)
        step0_out = replayer.replay_step(
            kind="tool_call",
            actor="sql_query",
            input_payload={"query": "SELECT sum(amount) FROM sales WHERE month = '2026-10'"},
        )
        assert step0_out["total_minor"] == 15000000
        print("CassetteReplayer: Replayed step 0 deterministically without live LLM calls")

        # 5. Telemetry: Export cassette to standard W3C OpenTelemetry spans for StackPulse/APM
        otel_spans = export_cassette_to_otel(recorder)
        assert len(otel_spans) == 4  # 1 root span + 3 step spans
        trace_id = otel_spans[0]["trace_id"]
        print(f"OTel Export: Generated {len(otel_spans)} W3C trace spans (TraceID={trace_id[:16]}...)")

    return {
        "linter_findings": len(report.findings),
        "steps_recorded": 3,
        "cassette_verified": True,
        "otel_spans": len(otel_spans),
    }


if __name__ == "__main__":
    main()
