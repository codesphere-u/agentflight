# CLAUDE.md — AgentFlight Engineering Guide

## Project Overview
`agentflight` is a zero-dependency, pure Python 3.10+ **AI Agent Black-Box Flight Recorder, Deterministic Trajectory Replay Engine, and 10-Rule MCP Tool-Smell Linter**. It provides sub-0.02ms, $0.00 token-spend CI regression testing for agent trajectories, real-time loop/cost circuit breakers, and static schema ergonomics auditing (`TS001`–`TS010`).

* **Package Name (PyPI)**: `agentflight` (CLI entry point: `agentflight`, module: `agentflight`)
* **MCP Specification**: Tripartite support for **Tools**, **Resources**, and **Prompts** (Protocol version `2024-11-05`).
* **Hosted Production**: `https://agentflight-tau.vercel.app/mcp` (Vercel Serverless Streamable HTTP + SSE).
* **Interactive Portal**: `https://agentflight-tau.vercel.app/` (Developer Playground).

---

## Build, Test & Lint Commands

```bash
# Run the complete test suite
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run the built-in reproducible benchmark suite
uv run python -m agentflight.cli benchmark

# Lint showcase tool definitions
uv run python -m agentflight.cli lint

# Run the end-to-end recording and replay demo
uv run python -m agentflight.cli demo

# Build sdist and wheel distributions
uv build

# Run local stdio MCP server
uv run python -m agentflight.cli serve-mcp
```

---

## Architecture & Code Structure

```text
src/agentflight/
├── __init__.py         # Package exports
├── recorder.py         # FlightRecorder: canonical SHA-256 chained trajectory recording
├── replayer.py         # CassetteReplayer: sub-0.02ms deterministic mock replayer
├── linter.py           # ToolSmellLinter: 10-rule MCP schema ergonomics analyzer (TS001-TS010)
├── breaker.py          # TrajectoryCircuitBreaker: real-time loop and token cost circuit breaker
├── evaluator.py        # TrajectoryEvaluator: differential regression detector between cassettes
├── otel_exporter.py    # OpenTelemetry / W3C TraceContext JSON span exporter
├── mcp_server.py       # AgentFlightMCPServer: Model Context Protocol JSON-RPC 2.0 engine
└── cli.py              # CLI commands (lint, demo, benchmark, diff, export-otel, serve-mcp)

api/
├── index.py            # Vercel Serverless FastAPI gateway (rate-limited, sandboxed)
└── portal.py           # Zero-dependency interactive Developer Portal & Playground
```

---

## Model Context Protocol (MCP) Primitives

### 1. Tools (`tools/list`, `tools/call`)
* `agentflight_lint_tools`: Statically audit MCP tool definitions against 10 ergonomics rules (`TS001`–`TS010`). Available on public hosted Vercel endpoint.
* `agentflight_diff_cassettes`: Compare baseline vs. candidate cassettes to detect tool sequence drift (stdio).
* `agentflight_export_otel`: Convert recorded trajectories into W3C TraceContext / OTel spans (stdio).
* `agentflight_verify_cassette`: Cryptographically verify the SHA-256 hash chain of a `.flight.json` cassette (stdio).

### 2. Resources (`resources/list`, `resources/read`)
* `agentflight://rules/catalog`: The 10-rule ergonomics catalog (`TS001`–`TS010`) with penalty weights.
* `agentflight://metrics/summary`: Execution benchmark snapshot (sub-0.02ms replay latency, 1,676 tools/sec).

### 3. Prompts (`prompts/list`, `prompts/get`)
* `lint-tool-definitions`: Guide an LLM agent to critique and refactor flawed MCP tool schemas.
* `review-agent-trajectory`: Structured post-mortem prompt to analyze an execution trace for loops or errors.

---

## Claude Code Quick-Connect

```bash
# Add to Claude Code project scope:
claude mcp add --transport http agentflight https://agentflight-tau.vercel.app/mcp

# Or user scope (globally across all projects):
claude mcp add --scope user --transport http agentflight https://agentflight-tau.vercel.app/mcp
```
