# AgentFlight (`agentflight`)

[![CI & Reliability Gate](https://github.com/codesphere-u/agentflight/actions/workflows/ci.yml/badge.svg)](https://github.com/codesphere-u/agentflight/actions/workflows/ci.yml)
[![Release v1.1.0](https://img.shields.io/badge/release-v1.1.0-blue.svg)](https://github.com/codesphere-u/agentflight/releases/tag/v1.1.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Zero External API Keys](https://img.shields.io/badge/dependencies-zero%20runtime%20deps-brightgreen.svg)](pyproject.toml)

**AI Agent Black-Box Flight Recorder, Deterministic Trajectory Replay (`<0.02 ms`, `$0.00` CI Spend), Differential Regression Detector, OpenTelemetry / W3C TraceContext Exporter (for `stackpulse`), Real-Time Loop/Cost Circuit Breaker & 10-Rule MCP Tool-Smell Linter.**

---

## Why AgentFlight Exists (The 2026 Agent Reliability Pain Point)

Production AI agent engineering in 2026 faces two compounding bottlenecks:

1. **Non-Deterministic, Expensive Multi-Step Agent Debugging & CI Testing**: When a 15-step tool-calling or MCP agent fails on step 12, re-running live LLM turns and external API calls in CI is slow (`10–45s`), flaky, and expensive. Engineers need a **"VCR / Black-Box Flight Recorder for AI Agents"** that captures every LLM turn, MCP RPC, and tool invocation into a tamper-evident SHA-256 hash chain cassette and replays the entire trajectory deterministically in **`<0.02 ms` with `$0.00` token spend**—raising a structural diff (`TrajectoryDivergenceError`) the instant an agent's behavior drifts from the golden baseline.
2. **"MCP Tool Smell" (Schema Ergonomics Bugs)**: Empirical evaluations across Model Context Protocol (MCP) servers and function-calling suites show that most tool-selection failures are caused not by model reasoning limits, but by poorly authored tool schemas: missing parameter descriptions, ambiguous boolean flags (`flag`, `mode`), deeply nested input objects (`depth > 3`), unconstrained finite-set strings (`status`, `format` without `enum`), overlapping tool names (`search_records` vs. `find_records`), and destructive tools (`delete_*`, `drop_*`) without confirmation guards.

**`agentflight`** solves both problems in a single, zero-dependency, pure-Python 3.10+ toolkit.

---

## Architecture Blueprint

```text
+-----------------------------------------------------------------------------------+
|                                   agentflight                                     |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. Pre-Deploy Static Gate                2. Runtime Execution & Guard            |
|  +----------------------------------+     +------------------------------------+  |
|  | ToolSmellLinter (linter.py)      |     | TrajectoryCircuitBreaker (guard.py)|  |
|  | - 10 Deterministic Rules         |     | - Exact Call Loop (N repeats)      |  |
|  |   (TS001 .. TS010)               |     | - Ping-Pong Cycle (A->B->A->B,     |  |
|  | - Agent Ergonomics Score (0-100) |     |   A->B->C->A->B->C)                |  |
|  | - Token Footprint Estimator      |     | - Consecutive Tool Error Storm     |  |
|  | - Actionable Remediations        |     | - Hard Token & USD Budget Caps     |  |
|  +-----------------+----------------+     +-----------------+------------------+  |
|                    |                                        |                     |
|                    v                                        v                     |
|  3. Tamper-Evident Flight Recorder        4. CI Replay & Golden Diff Engine       |
|  +----------------------------------+     +------------------------------------+  |
|  | FlightRecorder (recorder.py)     |     | CassetteReplayer & Evaluator       |  |
|  | - Append-only TrajectorySpan     | --> | - Sub-ms $0.00 Deterministic Stub  |  |
|  | - Canonical JSON SHA-256 Chain   |     | - Structural Diff on Divergence    |  |
|  |   (prev_hash -> step_hash)       |     | - Tool Precision / Recall / F1     |  |
|  | - .flight.json & .flight.jsonl   |     | - Step Efficiency & Cost Delta     |  |
|  | - verify_cassette() Tamper Check |     | - Goal Completion Score (0.0-1.0)  |  |
|  +----------------------------------+     +------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## Installation

```bash
pip install "git+https://github.com/codesphere-u/agentflight.git@v1.1.0"
# After the first PyPI release: pip install agentflight

# Contributors:
pip install -e ".[dev]"
```

---

## Quickstart

### 1. Record & Cryptographically Verify an Agent Trajectory (`FlightRecorder`)

```python
from agentflight import FlightRecorder, CassetteReplayer, verify_cassette

recorder = FlightRecorder(agent_id="sre-incident-agent", metadata={"env": "prod"})

recorder.record(
    kind="llm_turn",
    actor="planner_model",
    input_payload={"goal": "Investigate payment-api p99 latency spike"},
    output_payload={"next_tool": "prometheus.query_metrics"},
    latency_ms=410.0,
    prompt_tokens=580,
    completion_tokens=90,
    cost_usd=0.0022,
)
recorder.record(
    kind="mcp_rpc",
    actor="prometheus.query_metrics",
    input_payload={"service": "payment-api", "window": "15m"},
    output_payload={"p99_latency_ms": 1840.0, "anomaly": True},
    latency_ms=85.0,
)

# Persist as tamper-evident .flight.json or .flight.jsonl
recorder.save("cassettes/incident_8841.flight.json")
assert verify_cassette(recorder) is True
```

### 2. Replay Deterministically in `<0.02 ms` with `$0.00` Spend (`CassetteReplayer`)

```python
replayer = CassetteReplayer("cassettes/incident_8841.flight.json", strict_order=True)

# Stub any MCP or tool callable directly in pytest:
query_metrics_stub = replayer.stub_tool("prometheus.query_metrics", kind="mcp_rpc")

# Replaying matching steps returns recorded payloads in ~2.8 microseconds:
replayer.replay_step("llm_turn", "planner_model", {"goal": "Investigate payment-api p99 latency spike"})
result = query_metrics_stub(window="15m", service="payment-api")  # Key-order invariant!
assert result["anomaly"] is True
```

If a code change causes the agent to call the wrong tool or pass altered parameters, `CassetteReplayer` immediately raises `TrajectoryDivergenceError` with `missing_keys`, `extra_keys`, and `changed_values`.

### 3. Lint MCP Tool Schemas Across 10 Ergonomics Rules (`ToolSmellLinter`)

```python
from agentflight import ToolSmellLinter, SHOWCASE_FLAWED_MCP_TOOLS

linter = ToolSmellLinter()
report = linter.lint(SHOWCASE_FLAWED_MCP_TOOLS)

print(f"Ergonomics Score: {report.ergonomics_score}/100 (Grade {report.grade})")
for finding in report.findings:
    print(f"[{finding.rule_id}] {finding.tool_name}: {finding.message}")
    print(f"  Fix -> {finding.remediation}")
```

### 4. Guard Live Agents Against Loops, Ping-Pong Cycles & Runaway Spend (`TrajectoryCircuitBreaker`)

```python
from agentflight import TrajectoryCircuitBreaker, CircuitBreakerTripped

breaker = TrajectoryCircuitBreaker(
    max_identical_repeats=3,
    max_ping_pong_cycles=2,
    max_consecutive_errors=3,
    max_total_tokens=25_000,
    max_cost_usd=0.50,
)

try:
    breaker.observe("search_logs", {"query": "timeout"})
    breaker.observe("refine_query", {"query": "timeout"})
    breaker.observe("search_logs", {"query": "timeout"})
    breaker.observe("refine_query", {"query": "timeout"})  # Trips on A -> B -> A -> B!
except CircuitBreakerTripped as exc:
    print(exc.reason, exc.step_index, exc.evidence)
    # -> ping_pong_oscillation 3 {'period': 2, 'cycles': 2, 'pattern_actors': ['search_logs', 'refine_query']}
```

### 5. Compare Candidate vs. Golden Trajectories (`compare_cassettes` & `TrajectoryEvaluator`)

```python
from agentflight import compare_cassettes, diff_trajectories

# v1.1.0 Trajectory Differential Analyzer (Levenshtein/LCS sequence diff + loop/error/cost regression check)
report = compare_cassettes("cassettes/baseline.flight.jsonl", "cassettes/candidate.flight.jsonl")
print(report.regression_detected, report.similarity_score, report.added_tools, report.cost_delta_pct)
print(report.summary_markdown)

# Golden Evaluation Metrics (Precision, Recall, F1, Step Efficiency)
diff = diff_trajectories(golden_recorder, candidate_recorder)
print(diff.tool_precision, diff.tool_recall, diff.step_efficiency_ratio, diff.goal_completion_score)
```

### 6. Export W3C TraceContext / OpenTelemetry Spans for `stackpulse` (`export_cassette_to_otel`)

```python
from agentflight import export_cassette_to_otel

spans = export_cassette_to_otel(
    "cassettes/incident_8841.flight.json",
    service_name="sre-incident-agent",
    output_path="spans.json",
)
# Directly ingestible by `codesphere-u/stackpulse` for critical-path DAG analysis and SLO burn-rate monitoring!
```

---

## MCP Tool-Smell Rule Catalog (`TS001`–`TS010`)

| Rule ID | Severity | Penalty | Rule Title & Ergonomic Failure Mode |
| :--- | :--- | ---: | :--- |
| **`TS001`** | `ERROR` | `-12` | **Missing or Ultra-Short Tool Description (`<15` chars)**: Leaves the LLM guessing when to invoke the tool. |
| **`TS002`** | `WARNING` | `-5` | **Property Missing `description`**: A parameter inside `inputSchema.properties` has no semantic description or format hint. |
| **`TS003`** | `WARNING` | `-8` | **Deeply Nested Input Schema (`depth > 3`)**: Deep object nesting degrades JSON argument serialization accuracy on smaller/faster models. |
| **`TS004`** | `WARNING` | `-7` | **Excessive Top-Level Parameter Count (`> 8`)**: Increases parameter hallucination and omission rates. |
| **`TS005`** | `WARNING` | `-5` | **Ambiguous Boolean Flag Name**: Boolean named `flag`, `mode`, `option`, `data`, `value`, `switch`, or `toggle` without clear polarity. |
| **`TS006`** | `WARNING` | `-6` | **Unconstrained Finite-Set String Parameter**: Parameter named `status`, `sort`, `format`, `env`, `role`, `type`, or `priority` lacks `enum` or `pattern`. |
| **`TS007`** | `WARNING` | `-6` | **Missing `required` Array on Non-Empty Schema**: Causes models to omit mandatory arguments. |
| **`TS008`** | `ERROR` | `-10` | **High Lexical Overlap Between Tools (`cosine >= 0.72`)**: Overlapping tool names/descriptions in the same suite cause nondeterministic routing confusion. |
| **`TS009`** | `WARNING` | `-7` | **Bloated Schema Token Footprint (`> 450` tokens)**: Excessive schema verbosity inflates prompt cost on every agent turn. |
| **`TS010`** | `ERROR` | `-10` | **Destructive Tool Missing Safety Guard**: Tool prefixed with `delete_`, `drop_`, `remove_`, `transfer_`, or `exec_` lacks a `confirm`/`dry_run`/`idempotency_key` parameter or irreversibility warning. |

---

## Measured Benchmark Results

Reproducible via `python -m agentflight.cli benchmark` (measured on Python 3.12):

| Subsystem Operation | Workload Size | Total Latency (ms) | Per-Unit Latency | Throughput |
| :--- | :--- | ---: | ---: | ---: |
| `FlightRecorder.record` (SHA-256 chain) | 1,000 spans | 7.42 ms | 7.42 us/span | 134,770 spans/s |
| `verify_cassette` (Tamper Verification) | 1,000 spans | 3.40 ms | 3.40 us/span | 294,117 spans/s |
| `CassetteReplayer.replay_step` ($0 Stub) | 1,000 spans | 2.83 ms | 2.83 us/span | 353,356 spans/s |
| `TrajectoryCircuitBreaker.observe_span` | 1,000 spans | 3.01 ms | 3.01 us/span | 332,225 spans/s |
| `ToolSmellLinter.lint` (10 Rules + TS008) | 200 MCP tools | 119.27 ms | 596.35 us/tool | 1,676 tools/s |
| `TrajectoryEvaluator.diff_trajectories` | 1,000 vs 1,000 spans | 4.06 ms | 4.06 us/span | 246,305 spans/s |

---

## CLI Reference

```bash
# 1. Lint showcase flawed vs. hardened MCP tool suites (or pass --schema-file path/to/tools.json)
agentflight lint

# 2. Run the end-to-end recording, <0.02ms replay, circuit breaker & diff demo
agentflight demo

# 3. Run the reproducible subsystem benchmark suite
agentflight benchmark

# 4. Compare baseline vs. candidate cassettes for behavioral regressions (v1.1.0)
agentflight diff baseline.flight.jsonl candidate.flight.jsonl --json

# 5. Export cassette to W3C TraceContext / OpenTelemetry JSON spans for StackPulse (v1.1.0)
agentflight export-otel incident_8841.flight.json --output spans.json

# 6. Start the JSON-RPC 2.0 MCP Server over stdio (exposes agentflight_diff_cassettes, etc.)
agentflight serve-mcp
```

---

## Architectural Decision Records (ADRs)

### ADR-001: Canonical JSON SHA-256 Chaining for Trajectory Cassettes
- **Context**: Golden test fixtures for multi-step agents frequently suffer from dictionary key-order drift across Python/JSON runtimes and silent fixture edits.
- **Decision**: Every `TrajectorySpan` computes `input_hash` over `json.dumps(..., sort_keys=True, separators=(",", ":"))` and chains `step_hash = SHA256(step_index || kind || actor || input_payload || output_payload || status || prev_hash)`.
- **Consequence**: Reordered keyword arguments match deterministically during replay while any mutation to recorded inputs, outputs, or step ordering triggers `CassetteTamperError`.

### ADR-002: Zero-Dependency Static Ergonomics Linting (`TS001`–`TS010`)
- **Context**: Calling an LLM judge to critique MCP tool definitions is slow, non-deterministic in CI, and requires API credentials.
- **Decision**: Implement a fast, deterministic 10-rule static analyzer combining JSON Schema AST traversal with tokenized bag-of-words cosine similarity (`TS008`).
- **Consequence**: 200 MCP tool definitions are linted in `~119 ms` (`1,676 tools/sec`) with zero external dependencies.

---

## Hosted endpoint (Vercel)

A free, public, stateless deployment of AgentFlight runs over **MCP Streamable HTTP**:

| | |
|---|---|
| MCP endpoint | `https://agentflight-tau.vercel.app/mcp` (JSON-RPC 2.0 over `POST`) |
| Health probe | `https://agentflight-tau.vercel.app/health` |

```bash
curl -s -X POST https://agentflight-tau.vercel.app/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Client config (any Streamable-HTTP-capable MCP client):

```json
{ "mcpServers": { "agentflight": { "url": "https://agentflight-tau.vercel.app/mcp" } } }
```

**Hosted limitations:** Only `agentflight_lint_tools` is exposed. The cassette tools (`agentflight_diff_cassettes`, `agentflight_export_otel`, `agentflight_verify_cassette`) read/write local files and are **disabled on the hosted endpoint** — use the local stdio install.

The hosted gateway is [`api/index.py`](api/index.py); it enforces a 1 MB body limit, strict JSON-RPC envelopes and the tool restrictions above. Deploy your own copy with `npx vercel deploy --prod` (entrypoint is configured in `pyproject.toml` under `[tool.vercel]`).

## License

MIT License — Copyright (c) 2026 [Akandwanaho Ivan Alvin (`codesphere-u`)](https://github.com/codesphere-u).
