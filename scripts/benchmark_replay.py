#!/usr/bin/env python3
"""
scripts.benchmark_replay
========================
Reproducible Deterministic Replay Benchmark for AgentFlight Cassettes.

Measures microsecond-precision span advancing performance across multiple iterations
with zero network dependencies and zero token consumption.
"""

from __future__ import annotations

import os
import statistics
import tempfile
import time
from typing import List

from agentflight import CassetteReplayer, FlightRecorder


def run_benchmark(iterations: int = 500, spans_per_cassette: int = 50) -> None:
    # 1. Create a representative multi-turn agent cassette
    recorder = FlightRecorder(agent_id="benchmark-agent")
    for i in range(spans_per_cassette):
        recorder.record(
            kind="llm_turn" if i % 2 == 0 else "tool_call",
            actor="openany:MiniMax-M2.5" if i % 2 == 0 else f"openany:mcp:tool_{i}",
            input_payload={"step": i, "query": f"benchmark query payload {i}"},
            output_payload={"result": f"benchmark output payload {i}", "status": "ok"},
            latency_ms=150.0 + i,
            prompt_tokens=40,
            completion_tokens=20,
            cost_usd=0.00003,
        )

    with tempfile.NamedTemporaryFile(suffix=".flight.json", delete=False) as tmp:
        cassette_path = tmp.name
    recorder.save(cassette_path)

    # 2. Benchmark replay over configured iterations
    total_spans = spans_per_cassette * iterations
    span_durations_ns: List[int] = []

    try:
        for _ in range(iterations):
            replayer = CassetteReplayer(cassette_path)
            while not replayer.is_exhausted:
                t0 = time.perf_counter_ns()
                replayer.advance()
                t1 = time.perf_counter_ns()
                span_durations_ns.append(t1 - t0)
    finally:
        if os.path.exists(cassette_path):
            os.remove(cassette_path)

    span_durations_us = [d / 1000.0 for d in span_durations_ns]
    span_durations_us.sort()

    p50 = statistics.median(span_durations_us)
    p90 = span_durations_us[int(len(span_durations_us) * 0.90)]
    p99 = span_durations_us[int(len(span_durations_us) * 0.99)]
    mean = statistics.mean(span_durations_us)
    throughput = 1_000_000.0 / mean if mean > 0 else 0

    print("=====================================================================")
    print(f"AgentFlight Deterministic Replayer Benchmark ({total_spans:,} spans)")
    print("=====================================================================")
    print(f"  P50 Latency : {p50:.3f} μs / span")
    print(f"  P90 Latency : {p90:.3f} μs / span")
    print(f"  P99 Latency : {p99:.3f} μs / span")
    print(f"  Mean Latency: {mean:.3f} μs / span")
    print(f"  Throughput  : {throughput:,.0f} spans / second")
    print("  Network Cost: $0.00 (Zero external network requests)")
    print("=====================================================================")


if __name__ == "__main__":
    run_benchmark()
