"""Drop-in AgentFlight middleware example for OpenAI-compatible, Anthropic, or LangGraph agent loops.

Shows how to wrap any existing agent tool-calling loop with:
1. Pre-execution cost & loop circuit breaking (TrajectoryCircuitBreaker)
2. Tamper-evident cryptographic cassette recording (FlightRecorder)
3. Sub-millisecond $0.00 offline CI verification (CassetteReplayer)

Run:
    python examples/framework_middleware.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable

from agentflight import (
    CassetteReplayer,
    CircuitBreakerTripped,
    FlightRecorder,
    TrajectoryCircuitBreaker,
    verify_cassette,
)


def guarded_step(
    *,
    kind: str,
    actor: str,
    input_payload: dict[str, Any],
    fn: Callable[[dict[str, Any]], dict[str, Any]],
    recorder: FlightRecorder,
    guard: TrajectoryCircuitBreaker,
    estimated_cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Execute one LLM/tool step protected by pre-flight budget reservation and flight recording."""
    with guard.reserve_budget(estimated_cost_usd) as reservation:
        output_payload = fn(input_payload)
        reservation.commit(estimated_cost_usd)

    span = recorder.record(
        kind=kind,
        actor=actor,
        input_payload=input_payload,
        output_payload=output_payload,
        cost_usd=estimated_cost_usd,
    )
    guard.observe_span(span)
    return output_payload


def fake_langgraph_node(payload: dict[str, Any]) -> dict[str, Any]:
    """Stand-in for any LLM turn or LangGraph node (swap in your real SDK call)."""
    return {"answer": f"Checked status for {payload['service']}: healthy (p99=42ms)"}


def main() -> None:
    recorder = FlightRecorder(agent_id="framework-middleware-demo")
    guard = TrajectoryCircuitBreaker(max_cost_usd=0.05, max_identical_repeats=2)

    # 1. Normal guarded execution
    result = guarded_step(
        kind="llm_turn",
        actor="agent.supervisor",
        input_payload={"service": "payments-api"},
        fn=fake_langgraph_node,
        recorder=recorder,
        guard=guard,
        estimated_cost_usd=0.002,
    )
    print(f"Step 1 succeeded: {result['answer']}")

    # 2. Loop protection: repeating the exact same call twice triggers halt
    try:
        guarded_step(
            kind="llm_turn",
            actor="agent.supervisor",
            input_payload={"service": "payments-api"},
            fn=fake_langgraph_node,
            recorder=recorder,
            guard=guard,
            estimated_cost_usd=0.002,
        )
    except CircuitBreakerTripped as exc:
        print(f"Loop halted cleanly: {exc.reason}")

    # 3. Pre-execution budget block ($0.00 spent when cost exceeds cap)
    try:
        guarded_step(
            kind="llm_turn",
            actor="agent.expensive_planner",
            input_payload={"service": "full-audit"},
            fn=fake_langgraph_node,
            recorder=recorder,
            guard=guard,
            estimated_cost_usd=1.00,
        )
    except CircuitBreakerTripped as exc:
        print(f"Budget shield halted unaffordable call before dispatch: {exc.reason}")

    # 4. Persist & replay deterministically in CI with $0.00 API cost
    with tempfile.TemporaryDirectory() as tmp:
        cassette_path = Path(tmp) / "middleware_run.flight.json"
        recorder.save(cassette_path)
        loaded = FlightRecorder.load(cassette_path, verify=True)
        assert verify_cassette(loaded)

        replayer = CassetteReplayer(cassette_path)
        replayed = replayer.replay_step(
            kind="llm_turn",
            actor="agent.supervisor",
            input_payload={"service": "payments-api"},
        )
        assert replayed == result
        print("Offline CI replay verified ($0.00 spend, SHA-256 chain valid).")


if __name__ == "__main__":
    main()
