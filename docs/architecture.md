# AgentFlight System Architecture

## 1. Executive Summary

`agentflight` is an open-source, zero-dependency Python reliability and testing harness for multi-step AI agents and Model Context Protocol (MCP) clients. It addresses two primary challenges in production agent engineering:
1. **Non-Deterministic, Costly CI Re-runs**: Flaky agent test runs cost dollars and minutes per CI build. `agentflight` records multi-step agent trajectories into cryptographic SHA-256 cassettes and enables deterministic mock-free replaying in `<0.02 ms` per step with `$0.00` spend.
2. **MCP Tool Ergonomics Degradation**: Evaluates schemas against 10 deterministic lint rules to prevent common prompt failures caused by poorly specified JSON schemas.

---

## 2. Architectural Blueprint

```text
+-----------------------------------------------------------------------------------+
|                                   agentflight                                     |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. Pre-Deploy Static Gate                2. Runtime Execution & Guard            |
|  +----------------------------------+     +------------------------------------+  |
|  | ToolSmellLinter (linter.py)      |     | TrajectoryCircuitBreaker (guard.py)|  |
|  | - 10 Deterministic Rules         |     | - Exact Call Loop (N repeats)      |  |
|  |   (TS001 .. TS010)               |     | - Ping-Pong Cycle (A->B->A->B)     |  |
|  | - Agent Ergonomics Score (0-100) |     | - Consecutive Tool Error Storm     |  |
|  | - Token Footprint Estimator      |     | - Hard Token & USD Budget Caps     |  |
|  +-----------------+----------------+     +-----------------+------------------+  |
|                    |                                        |                     |
|                    v                                        v                     |
|  3. Tamper-Evident Flight Recorder        4. CI Replay & Golden Diff Engine       |
|  +----------------------------------+     +------------------------------------+  |
|  | FlightRecorder (recorder.py)     |     | CassetteReplayer & Evaluator       |  |
|  | - Append-only TrajectorySpan     | --> | - Sub-ms $0.00 Deterministic Stub  |  |
|  | - Canonical JSON SHA-256 Chain   |     | - Structural Diff on Divergence    |  |
|  | - .flight.json & .flight.jsonl   |     | - Step Efficiency & Cost Delta     |  |
|  | - verify_cassette() Tamper Check |     | - Goal Completion Score            |  |
|  +-----------------+----------------+     +-----------------+------------------+  |
|                    |                                        |                     |
|                    +--------------------+-------------------+                     |
|                                         |                                         |
|                                         v                                         |
|                     5. Telemetry & Cross-Platform Ingestion                       |
|                     +---------------------------------------+                     |
|                     | OpenTelemetry W3C TraceContext Exporter|                     |
|                     | - stackpulse Ingestion Connector      |                     |
|                     | - JSON-LD / OTLP Spans                |                     |
|                     +---------------------------------------+                     |
+-----------------------------------------------------------------------------------+
```

---

## 3. Core Modules

### 3.1 FlightRecorder (`src/agentflight/recorder.py`)
- Records agent turns as `TrajectorySpan` objects capturing inputs, tool names, parameters, outputs, token counts, and execution duration.
- Builds an append-only SHA-256 Merkle chain linking each step (`prev_hash` to `step_hash`) using canonical JSON serialization.
- Provides `verify_cassette()` to detect post-execution tampering.

### 3.2 CassetteReplayer & Evaluator (`src/agentflight/replayer.py`, `evaluator.py`)
- Emulates live agent environments in CI by matching incoming tool requests against pre-recorded cassette steps.
- Raises `TrajectoryDivergenceError` with visual diffs whenever tool arguments, sequencing, or outputs drift from baseline.
- Computes goal completion score, precision, recall, and cost differential.

### 3.3 TrajectoryCircuitBreaker (`src/agentflight/guard.py`)
- **Loop Protection**: Aborts runaway agent calls matching exact consecutive patterns (e.g. repeated queries).
- **Cycle Detection**: Detects alternating ping-pong tool cycles (e.g., $A \rightarrow B \rightarrow A \rightarrow B$).
- **Budget Caps**: Enforces hard token limits and dollar expenditure limits mid-execution.

### 3.4 ToolSmellLinter (`src/agentflight/linter.py`)
- Analyzes JSON Schema definitions across 10 rules:
  - `TS001`: Tool missing clear docstring / description.
  - `TS002`: Property missing description.
  - `TS003`: Ambiguous boolean parameter names.
  - `TS004`: Overly deep schema nesting (`depth > 3`).
  - `TS005`: String property without enum constraints when finite set is implied.
  - `TS006`: High similarity tool names (risk of hallucinated invocation).
  - `TS007`: Destructive action tool without confirmation parameter.
  - `TS008`: Excessive required parameter count (`> 7`).
  - `TS009`: Excessive overall token size per tool schema.
  - `TS010`: Inconsistent casing across properties.

### 3.5 OpenTelemetry & W3C Exporter (`src/agentflight/otel.py`)
- Maps flight trajectories directly to W3C TraceContext standard spans (`traceparent`, `tracestate`).
- Integrates seamlessly with `stackpulse` and standard APM observability pipelines.

---

## 4. Verification and Reliability Standards

- **90/90 Unit & Regression Tests**: Verified across Python 3.10, 3.11, 3.12, and 3.13.
- **Zero Runtime Dependencies**: No external HTTP libraries or network sockets needed for local recording and replay.
