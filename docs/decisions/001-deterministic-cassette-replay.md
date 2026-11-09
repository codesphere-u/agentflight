# ADR 001: Deterministic Replay and Cryptographic Cassettes for Agent CI

## Status
Accepted

## Context
Automated testing for multi-step AI agents is fundamentally hindered by non-determinism, network latency, and continuous API costs. When an agent requires 10 to 20 tool invocations to complete a task, running live end-to-end tests in CI pipelines:
- Incurs significant token bills per pull request.
- Introduces random flakiness due to LLM sampling temperature and third-party API rate limits.
- Makes pinpointing regressions in prompt engineering or tool schemas difficult.

We need a deterministic mechanism to record golden trajectory traces and replay them during CI without network calls or LLM spend.

## Decision
We implemented a **Cryptographic Cassette Replay** framework inspired by HTTP VCRs, adapted for multi-turn agent execution:
1. **Append-Only Merkle Chain**:
   - Each trajectory step is recorded as a `TrajectorySpan` containing input arguments, outputs, timestamps, and tool name.
   - A rolling SHA-256 hash chains each step to its predecessor (`step_hash = sha256(prev_hash + canonical_json(step_payload))`), guaranteeing cassette tamper-evidence.
2. **Deterministic Replay Stub**:
   - In replay mode, agent tool invocations are matched against recorded cassette steps.
   - Returns saved results in `<0.02 ms` without hitting network services or LLM endpoints.
3. **Structural Divergence Detection**:
   - If an agent generates an unexpected tool call or differing parameter payload, the replayer immediately raises `TrajectoryDivergenceError` detailing the exact delta.
4. **Zero Runtime Dependencies**:
   - The recording and replay system uses only the Python standard library (`hashlib`, `json`, `dataclasses`).

## Consequences
### Positive
- Zero token costs during pull request and CI runs.
- Sub-second test execution speeds across complex multi-step trajectories.
- Instant, unambiguous diffs identifying where an agent drifted from the golden path.
- Cassette files (`.flight.json`) can be checked into git as regression test fixtures.

### Negative / Trade-offs
- If an upstream tool API legitimately changes its schema, the cassette must be re-recorded.
- Requires agents to pass tool calls through the `FlightRecorder` wrapper or interceptor.
