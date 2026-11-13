# Changelog

All notable changes to `agentflight` are documented in this file.

## [1.4.0] - 2026-11-13

### Enterprise & Operational Readiness
- **Automatic PII & Secret Redaction (`src/agentflight/redact.py`, `src/agentflight/recorder.py`)**:
  - Added pure-stdlib secret scrubber (`redact_sensitive`, `redact_text`, `redact_cassette`, `contains_sensitive_data`) removing API keys (`sk-...`, `sk-ant-...`, `sk-proj-...`, `oa_...`, `ghp_...`, `AKIA...`), Bearer tokens, JWTs, URL basic-auth credentials, cookies, and auth headers while preserving token-count metrics and JSON schemas.
  - Enabled `FlightRecorder(..., redact_secrets=True)` by default BEFORE SHA-256 chain hashing and updated `CassetteReplayer.replay_step()` to match both raw and redacted input digests for deterministic key-rotated replay.
- **Prometheus `/metrics`, Request Tracing & Distributed Rate Limiting (`src/agentflight/telemetry.py`, `api/index.py`, `src/agentflight/http_server.py`)**:
  - Added shared thread-safe `ServerMetrics` exposed at `GET /metrics` (Prometheus text exposition or JSON when `Accept: application/json`) across both Vercel ASGI and standalone HTTP servers.
  - Propagated validated `X-Request-ID` headers (`resolve_request_id`), added `HEAD` readiness responses on health/metrics endpoints, opt-in structured JSON logging (`AGENTFLIGHT_LOG_JSON=1`), and optional zero-dep Upstash Redis REST distributed rate limiting (`UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`) with automatic fail-open memory fallback.
- **Self-Diagnostics & Robustness (`src/agentflight/cli.py`, `src/agentflight/wrappers.py`, `src/agentflight/linter.py`, `.github/workflows/smoke-production.yml`)**:
  - Added `agentflight doctor [--json]` verifying Python version, zero-dep stdlib core imports, lazy `pytest11` plugin registration, SHA-256 chain + redaction integrity, and circuit breaker tripping.
  - Coalesced streamed OpenAI `tool_calls` deltas by index (`_merge_tool_call_deltas`) inside `_StreamAccumulator`, guarded `_normalize_tool_def` against malformed non-dict schemas, fixed `.github/workflows/smoke-production.yml` triggers, and raised CI coverage gate to `--cov-fail-under=90` (`167` passing tests, `90.57%` coverage).

## [1.3.1] - 2026-11-13

### Production Hardening
- **Thread-Safe Recording & Atomic Cassette Saves (`src/agentflight/recorder.py`)**:
  - Protected `FlightRecorder` (`RLock`) and `CassetteReplayer` (`Lock`) mutations and cursor state for concurrent multi-threaded execution.
  - Added atomic `FlightRecorder.save()` via temporary file + `fsync` + `os.replace()` preventing partial/corrupted cassettes on crash, and translated corrupt cassette parsing into `CassetteTamperError`.
- **Sync & Async Streaming SDK Wrappers (`src/agentflight/wrappers.py`)**:
  - Added full `stream=True` iterator/context-manager proxies (`_SyncStreamWrapper`, `_AsyncStreamWrapper`, `_StreamAccumulator`) capturing streamed text deltas, tool-call chunks, token usage, partial error recovery, and offline stream replay across OpenAI Chat, OpenAI Responses, and Anthropic Messages.
  - Added thread lock synchronization inside `FlightCallbackHandler`.
- **Single-Source Versioning & Server Security Hardening (`src/agentflight/_version.py`, `src/agentflight/http_server.py`, `src/agentflight/mcp_server.py`, `api/index.py`)**:
  - Unified `SERVER_VERSION` across `__init__.py`, `mcp_server.py`, `http_server.py`, and `api/index.py`.
  - Enforced `Content-Length` validation and configurable `AGENTFLIGHT_MAX_BODY_BYTES` (`413` on oversized requests), JSON-RPC `params` dict validation (`-32602`), security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`), configurable `MCP_ALLOWED_ORIGINS`, and broken-pipe resilience in `http_server.py`.
- **Zero-Overhead Lazy `pytest11` Shimming & 83% Coverage Gate (`src/_agentflight_pytest.py`, `.github/workflows/ci.yml`)**:
  - Added lazy `_agentflight_pytest` entry point shim eliminating eager startup imports and early-coverage warnings (`--cov-fail-under=80` + `mypy src/agentflight api` enforced in CI; 157 passing tests).

## [1.3.0] - 2026-11-13

### Added
- **1-Line Drop-In SDK Wrappers (`src/agentflight/wrappers.py`)**:
  - `wrap_openai(client, ...)` (supports `OpenAI`, `AsyncOpenAI`, OpenRouter, vLLM, and OpenAny clients via both `.chat.completions.create` and `.responses.create`).
  - `wrap_anthropic(client, ...)` (supports `Anthropic` and `AsyncAnthropic` `.messages.create`).
  - `wrap_callable(fn, ...)` and `FlightCallbackHandler` (sync/async decorators and duck-typed LangChain / LangGraph / OpenAny lifecycle callbacks).
- **Auto-Registered Pytest Plugin (`src/agentflight/pytest_plugin.py`)**:
  - Registered via `pytest11` entry point (`agentflight-mcp` install automatically activates it in pytest).
  - Provides built-in fixtures (`flight_recorder`, `flight_guard`, `flight_session`), `@pytest.mark.flight_cassette(path, mode="auto")`, `@pytest.mark.flight_guard(...)`, and `--flight-mode` / `--flight-dir` CLI flags.
- **Visual `.flight.json` Timeline Replay Viewer (`api/portal.py`)**:
  - Added interactive cassette timeline & chain-linkage inspector to the hosted web portal with file upload, paste support, sample incident presets, latency bars, USD spend, and SHA-256 chain continuity verification.
- **Fast PyPI `uvx` Startup (`smithery.yaml`, `README.md`)**:
  - Switched `uvx` and Smithery commands from git-cloning the repository to pulling the prebuilt PyPI distribution (`uvx --from agentflight-mcp agentflight serve-mcp`).
- **Static Quality & CI Gates (`.github/workflows/ci.yml`, `pyproject.toml`)**:
  - Added `ruff` (`E`, `F`, `I`) and `mypy` type-checking gates to CI alongside the full pytest suite (149 passing tests).

### Fixed
- Fixed `@property` access (`total_cost_usd`, `total_tokens`) and `compare_cassettes` drift reporting in `FlightSession(mode="diff")` (`src/agentflight/testing.py`).

## [1.2.0] - 2026-11-11

### Added
- **Official OpenAny Commercial Integration & Revenue Attribution (`src/agentflight/providers/openany.py`)**:
  - Gated attribution header `X-OpenAny-Partner-Id: agentflight` sent on all model and tool requests to `*.openany.si` domains, powering a permanent 30% revenue sharing partnership with OpenAny.
  - Strict domain boundary isolation (`is_openany_domain`) preventing partner headers and API keys from leaking to third-party endpoints.
  - Live Server-Sent Events (SSE) streaming support via `provider.stream_chat(...)`.
  - Remote MCP tool discovery (`discover_mcp_tools`) and tool ergonomics linting (`lint_openany_tools`) against rules TS001–TS010.
- **Thread-Safe Budget Reservations (`TrajectoryCircuitBreaker` in `src/agentflight/guard.py`)**:
  - Added `reserve_budget(amount_usd)` returning a `BudgetReservation` context manager.
  - Guarantees thread-safe budget protection in concurrent agent runs, eliminating race conditions that could exceed spend caps.
- **Microsecond Replay Benchmark (`scripts/benchmark_replay.py`)**:
  - Benchmarked sub-microsecond span replay at **0.08 μs per span** (>11M spans/sec) with zero network calls and $0.00 cost.
- **Live Commercial Telemetry & Verification (`docs/LIVE_ATTRIBUTION_RECORD.md`)**:
  - Executed and recorded controlled micro-request `0743400fadffb4e5fa37eacbe28eb0fa` to MiniMax-M2.5 for backend attribution confirmation.
- **Complete Commercial Launch Materials (`marketing/openany-launch/`)**:
  - Runnable interactive demo script: `scripts/demo_openany_commercial.py`.
  - Video shot list, announcements for X and LinkedIn, founder note, press release, and technical case study.
- **Ownership Clarification**:
  - Gated project ownership to **Akandwanaho Ivan Alvin** as an independently owned open-source AI infrastructure project.

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
