# AgentFlight System Architecture (`v1.6.0`)

## 1. Executive Summary

`agentflight` is an open-source, zero-runtime-dependency Python 3.10+ reliability, security, and deterministic testing platform for multi-step AI agents and Model Context Protocol (MCP) tool suites (`src/agentflight/` uses only the Python standard library; FastAPI/Uvicorn power the optional hosted Vercel ASGI portal in `api/index.py`).

It unifies **six verification & safety layers** in one package:
1. **Static Schema Ergonomics Gate (`TS001`–`TS010`) & Optimizer** (`linter.py`, `schema_optimizer.py`)
2. **Real-Time Loop/Budget Circuit Breaker (`CB001`–`CB005`)** (`guard.py`)
3. **Pre-Execution Runtime Policy Firewall (`PF001`–`PF007`)** (`policy.py`)
4. **Tamper-Evident SHA-256 Flight Recorder w/ Auto-Redaction** (`recorder.py`, `redact.py`)
5. **Deterministic Replay, Time-Travel Forking & Behavioral Contracts** (`recorder.py`, `assertions.py`, `diff.py`, `eval.py`, `testing.py`, `pytest_plugin.py`)
6. **Incident Post-Mortems, OpenTelemetry Export & 8-Tool MCP Server** (`post_mortem.py`, `otel_export.py`, `mcp_server.py`, `http_server.py`, `telemetry.py`)

---

## 2. Architectural Blueprint

```text
+---------------------------------------------------------------------------------------+
|                                    agentflight v1.6.0                                 |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  1. Pre-Deploy Static Gate                2. Pre-Execution Guard + Policy Firewall    |
|  +----------------------------------+     +----------------------------------------+  |
|  | linter.py & schema_optimizer.py  |     | guard.py + policy.py                   |  |
|  | - 10 Rules (TS001 .. TS010)      |     | - Loops, ping-pong, token/USD (CB001-5)|  |
|  | - Cosine collision check (TS008) |     | - SSRF, SQL DDL, traversal, secrets    |  |
|  | - Automated schema repair (fix)  |     |   & read-only gates (PF001 .. PF007)   |  |
|  +-----------------+----------------+     +-------------------+--------------------+  |
|                    |                                          |                       |
|                    v                                          v                       |
|  3. Black-Box Flight Recorder             4. Replay, Time-Travel Fork & Contracts     |
|  +----------------------------------+     +----------------------------------------+  |
|  | recorder.py + redact.py          | --> | recorder.py + assertions.py + diff.py  |  |
|  | - Scrub secrets BEFORE hashing   |     | - <0.02 ms $0.00 deterministic stubs   |  |
|  | - Canonical JSON SHA-256 chain   |     | - fork_from / fork_at counterfactuals   |  |
|  | - Atomic save (temp + fsync)     |     | - FlightContract behavioral SLAs       |  |
|  | - .flight.json & .flight.jsonl   |     | - Levenshtein/LCS Golden Diff Engine   |  |
|  +-----------------+----------------+     +-------------------+--------------------+  |
|                    |                                          |                       |
|                    +--------------------+---------------------+                       |
|                                         |                                             |
|                                         v                                             |
|                  5. Forensics, Telemetry & MCP Transport Layer                        |
|                  +-----------------------------------------------+                    |
|                  | - post_mortem.py (AAIB/NTSB reports)          |                    |
|                  | - otel_export.py (W3C TraceContext spans)     |                    |
|                  | - mcp_server.py (8 tools, stdio & HTTP/SSE)   |                    |
|                  | - api/index.py (Stateless Vercel ASGI host)   |                    |
|                  +-----------------------------------------------+                    |
+---------------------------------------------------------------------------------------+
```

---

## 3. Core Module Map (`src/agentflight/`)

| Module | Responsibilities |
| :--- | :--- |
| `recorder.py` | Thread-safe `FlightRecorder` (`RLock`), `TrajectorySpan`, canonical JSON SHA-256 Merkle chain (`prev_hash -> step_hash`), atomic `save()` (`NamedTemporaryFile` + `fsync` + `os.replace`), `verify_cassette()`, `CassetteReplayer`, `from_cassette_dict`, `fork_from`, and `fork_at`. |
| `redact.py` | Pure-stdlib secret scanner & scrubber (`redact_sensitive`, `redact_text`, `redact_cassette`, `contains_sensitive_data`) executing **before** SHA-256 hashing. |
| `guard.py` | `TrajectoryCircuitBreaker` (`CB001`–`CB005`), thread-safe `reserve_budget()`, optional `policy=TrajectoryPolicyEngine(...)` pre-execution gate. |
| `policy.py` | `TrajectoryPolicyEngine` (`PF001`–`PF007`), `PolicyRule`, `PolicyDecision`, `PolicyViolationError`, `audit_cassette()`. |
| `assertions.py` | Declarative `FlightContract`, `ContractReport`, `RuleResult`, and `assert_trajectory()`. |
| `linter.py` | 10-rule `ToolSmellLinter` (`TS001`–`TS010`) including tokenized bag-of-words cosine similarity (`TS008`), schema depth/token footprint estimation, and destructive guard checks. |
| `schema_optimizer.py` | `ToolSchemaOptimizer` rewriting weak MCP schemas into high-ergonomics Gold Standard definitions. |
| `diff.py` & `eval.py` | `compare_cassettes` (`TrajectoryDiffReport` with Levenshtein/LCS sequence diff) and `diff_trajectories` (Precision, Recall, F1, Goal Completion). |
| `post_mortem.py` | `FlightPostMortemAnalyzer` generating AAIB/NTSB Markdown & JSON incident reports. |
| `otel_export.py` | W3C TraceContext / OpenTelemetry `gen_ai.*` span exporter compatible with StackPulse, Jaeger, Datadog, and Tempo. |
| `wrappers.py` | Sync/async drop-in proxies (`wrap_openai`, `wrap_anthropic`, `wrap_callable`, `FlightCallbackHandler`) with `stream=True` delta coalescing. |
| `testing.py` & `pytest_plugin.py` | `@flight_test` decorator, `FlightSession` (including `assert_contract()`), and lazy `pytest11` fixtures (`flight_recorder`, `flight_guard`, `flight_session`). |
| `mcp_server.py` & `http_server.py` | 8-tool MCP JSON-RPC 2.0 stdio + standalone HTTP/SSE server exposing `/health` and Prometheus `/metrics`. |
| `telemetry.py` | Shared thread-safe `ServerMetrics`, `X-Request-ID` propagation, and optional Upstash Redis REST rate limiting. |

---

## 4. Exact 22-Rule Guardrail Taxonomy

### Static MCP Schema Rules (`TS001`–`TS010`)
- `TS001` (`ERROR`, `-12`): Missing or ultra-short tool description (`< 15` chars).
- `TS002` (`WARNING`, `-5`): Parameter inside `inputSchema.properties` missing `description`.
- `TS003` (`WARNING`, `-8`): Deeply nested `inputSchema` (`depth > 3`).
- `TS004` (`WARNING`, `-7`): Excessive top-level properties (`> 8`).
- `TS005` (`WARNING`, `-5`): Ambiguous boolean flag (`flag`, `mode`, `option`, `data`, `value`, `switch`, `toggle`).
- `TS006` (`WARNING`, `-6`): Unconstrained finite-set string (`status`, `sort`, `format`, `env`, `role`, `type`, `priority` lacking `enum`/`pattern`).
- `TS007` (`WARNING`, `-6`): Missing `required` array on non-empty schema.
- `TS008` (`ERROR`, `-10`): High lexical overlap between tool pairs (`cosine >= 0.72`).
- `TS009` (`WARNING`, `-7`): Bloated schema token footprint (`> 450` tokens).
- `TS010` (`ERROR`, `-10`): Destructive tool (`delete_*`, `drop_*`, `remove_*`, `transfer_*`, `exec_*`) missing confirmation/dry-run guard or warning.

### Runtime Circuit Breakers (`CB001`–`CB005`)
- `CB001`: Exact consecutive call repeat limit (`max_identical_repeats`).
- `CB002`: Ping-pong oscillation cycle detector (`A->B->A->B` / 3-step cycles).
- `CB003`: Consecutive tool error storm breaker (`max_consecutive_errors`).
- `CB004`: Thread-safe USD spend cap & `reserve_budget()` (`max_cost_usd`).
- `CB005`: Hard total prompt + completion token cap (`max_total_tokens`).

### Runtime Policy Firewall (`PF001`–`PF007`)
- `PF001`: Tool allowlist / blocklist enforcement.
- `PF002`: Read-only flight & destructive-tool gate.
- `PF003`: SSRF, private network & cloud metadata URL block (`169.254.169.254`, localhost, RFC1918).
- `PF004`: Path traversal (`../`) & sensitive OS path block.
- `PF005`: Destructive SQL (`DROP`, `TRUNCATE`, unguarded `DELETE`) block.
- `PF006`: Unredacted API key, Bearer token, or JWT secret exfiltration block.
- `PF007`: Per-flight mutating-call mutation budget ceiling (`max_mutations`).
