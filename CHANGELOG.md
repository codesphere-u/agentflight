# Changelog

All notable changes to `agentflight` are documented in this file.

## [1.1.0] - 2026-11-07

### Added
- **Trajectory Differential Analyzer & Regression Detector (`src/agentflight/diff.py`)**:
  - `compare_cassettes()` and `TrajectoryDifferentialAnalyzer` comparing baseline vs. candidate cassettes across model and prompt upgrades.
  - Computes Wagner-Fischer Levenshtein edit distance (`compute_levenshtein_distance`) and Longest Common Subsequence (`compute_lcs_length`) over tool call sequences.
  - Detects new tool execution errors, loop/oscillation regressions via `TrajectoryCircuitBreaker`, token & USD cost deltas (`cost_delta_pct`, `token_delta_pct`), latency deltas (`latency_delta_pct`), and final output structural drift.
  - Emits an immutable `TrajectoryDiffReport` with `regression_detected`, `similarity_score`, `added_tools`, `removed_tools`, and `summary_markdown`.
- **OpenTelemetry / W3C TraceContext Span Exporter (`src/agentflight/otel_export.py`)**:
  - `export_cassette_to_otel()` converting recorded `AgentFlight` cassette spans into W3C TraceContext / OpenTelemetry JSON spans (`trace_id`, `span_id`, `parent_span_id`, `service_name`, `operation_name`, `start_time_ms`, `duration_ms`, `status_code`, `attributes`) directly ingestible by [`codesphere-u/stackpulse`](https://github.com/codesphere-u/stackpulse) for critical-path DAG analysis and multi-window SLO burn-rate monitoring.
- **CLI & MCP Server Extensions (`cli.py`, `mcp_server.py`)**:
  - Added `agentflight diff <baseline> <candidate> [--json]` and `agentflight export-otel <cassette> [--output spans.json]` CLI subcommands.
  - Added `AgentFlightMCPServer` (`agentflight serve-mcp`) exposing `agentflight_diff_cassettes`, `agentflight_export_otel`, `agentflight_lint_tools`, and `agentflight_verify_cassette`.
- **Test Suite Expansion**:
  - Added 17 new unit and integration tests in `tests/test_diff_and_otel.py` (bringing the test suite from 73 to **90 passing tests**).

## [1.0.0] - 2026-11-07

### Added
- Initial release of `agentflight`:
  - `FlightRecorder` and `verify_cassette` with canonical JSON SHA-256 hash chaining.
  - `CassetteReplayer` for sub-millisecond (`<0.02 ms`), `$0.00` deterministic trajectory replay and `TrajectoryDivergenceError` structural diffing.
  - `ToolSmellLinter` enforcing 10 deterministic MCP tool schema ergonomics rules (`TS001`–`TS010`).
  - `TrajectoryCircuitBreaker` guarding against exact call loops, 2-step and 3-step ping-pong oscillations, consecutive error storms, and token/cost budget overruns.
  - `TrajectoryEvaluator` for golden trajectory precision, recall, F1, and efficiency scoring.
