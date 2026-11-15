# Getting Started with AgentFlight (`v1.6.0`)

Welcome to **AgentFlight** — an open-source, zero-dependency Python black-box flight recorder, `$0.00` CI deterministic replayer & time-travel forker, loop/cost circuit breaker, runtime safety policy firewall (`PF001`–`PF007`), behavioral contract engine, and 10-rule MCP tool-smell linter.

> **Interactive Studio & Copy-Ready Docs:** Try every tool directly in your browser at **[`https://codesphere-u.github.io/agentflight/studio.html`](https://codesphere-u.github.io/agentflight/studio.html)** or read the web manual at **[`https://codesphere-u.github.io/agentflight/docs.html`](https://codesphere-u.github.io/agentflight/docs.html)**.

---

## 1. Install & Self-Check in 10 Seconds

```bash
pip install agentflight-mcp
agentflight doctor --json
```

Verify everything end-to-end without API keys:

```bash
agentflight demo
agentflight lint
```

Or run zero-install with `uvx`:

```bash
uvx --from agentflight-mcp agentflight doctor
```

---

## 2. Choose Your Role

### Track A — AI Application Engineers (Wrap SDKs & Block Unsafe Calls)

Wrap `OpenAI`, `AsyncOpenAI`, OpenRouter, vLLM, OpenAny, or `Anthropic` in one line with a combined loop/cost guard and Runtime Policy Firewall:

```python
from openai import OpenAI
from agentflight import (
    TrajectoryCircuitBreaker,
    TrajectoryPolicyEngine,
    wrap_openai,
)

policy = TrajectoryPolicyEngine(mode="strict", max_mutations=2)
guard = TrajectoryCircuitBreaker(max_cost_usd=0.25, policy=policy)

client = wrap_openai(OpenAI(), guard=guard)
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Check service health"}],
)
client.agentflight_recorder.save("tests/cassettes/health.flight.json")
```

API keys (`sk-...`, `sk-ant-...`, `ghp_...`, `AKIA...`, Bearer tokens, JWTs) are automatically scrubbed **before** computing SHA-256 hashes, making cassettes safe to commit to Git.

---

### Track B — QA & CI Engineers (`$0.00` Replay, Time-Travel Forking & Contracts)

Installing `agentflight-mcp` registers the `pytest11` plugin (`flight_recorder`, `flight_guard`, `flight_session`, `@pytest.mark.flight_cassette`):

```python
import pytest
from agentflight import FlightContract

@pytest.mark.flight_cassette("tests/cassettes/checkout.flight.json")
def test_checkout_deterministic(flight_session):
    search = flight_session.stub("search_catalog", fallback_fn=lambda q: {"hits": [q]})
    assert search(q="router")["hits"] == ["router"]

    report = flight_session.assert_contract(
        FlightContract("checkout")
        .must_call("search_catalog")
        .max_cost_usd(0.10)
        .zero_errors()
        .require_valid_hash_chain()
    )
    assert report.passed
```

Run replay and trajectory gating in CI with `$0.00` LLM spend:

```bash
pytest -v --flight-mode=replay
agentflight diff baseline.flight.json candidate.flight.json --similarity-threshold 0.85
agentflight contract candidate.flight.json --must-call search_catalog --max-cost 0.10
agentflight replay candidate.flight.json --fork-at 1 --fork-out patched.flight.json
```

---

### Track C — Security & Platform Engineers (Audit Policy & Incident Post-Mortems)

Audit saved agent trajectories for SSRF (`PF003`), path traversal (`PF004`), destructive SQL (`PF005`), and unredacted secrets (`PF006`), or generate AAIB/NTSB post-mortem reports:

```bash
agentflight policy-audit runs/agent.flight.json --mode strict --json
agentflight post-mortem runs/agent.flight.json --output POST_MORTEM.md
agentflight export-otel runs/agent.flight.json --output spans.json
```

---

### Track D — MCP Server Authors (Lint, Optimize & Expose Tools)

Audit your tool schemas against `TS001`–`TS010` and auto-fix weak schemas to Gold Standard:

```bash
agentflight lint --schema-file tools.json
agentflight fix tools.json --output hardened_tools.json
```

Or connect Claude Code / Cursor directly to the hosted 5-tool endpoint (`https://agentflight-tau.vercel.app/mcp`) or full 8-tool local stdio server (`agentflight serve-mcp`). See [`MCP_AND_AGENTS.md`](MCP_AND_AGENTS.md).

---

## Core CLI Subcommands (`v1.6.0`)

| Command | Purpose |
| :--- | :--- |
| `agentflight doctor [--json]` | Run 6 self-diagnostics covering Python, stdlib core, pytest11, redaction/SHA-256, circuit breaker & policy/contracts |
| `agentflight demo` | Offline end-to-end showcase of recording, replay, loop tripping & diffing |
| `agentflight lint [--schema-file]` | Audit built-in or custom MCP tool definitions across `TS001`–`TS010` |
| `agentflight fix <file>` | Auto-repair smelly MCP schemas to Gold Standard |
| `agentflight replay <cassette>` | Deterministic offline replay + `--fork-at` counterfactual cassette branching |
| `agentflight policy-audit <cassette>` | Offline Runtime Policy Firewall (`PF001`–`PF007`) security audit |
| `agentflight contract <cassette>` | Enforce declarative `FlightContract` assertions & budgets |
| `agentflight ci` | Unified CI gate (`--schema-file`, `--cassette`, `--contract`, `--policy-mode`, `--github-summary`) |
| `agentflight diff <base> <cand>` | Levenshtein/LCS sequence diff + cost/token/error regression detection |
| `agentflight post-mortem <cassette>` | AAIB/NTSB incident Markdown or JSON root-cause report |
| `agentflight export-otel <cassette>` | Export W3C TraceContext spans (`gen_ai.*`) for StackPulse, Jaeger & Datadog |
| `agentflight serve-mcp` / `serve-http` | Start the 8-tool MCP server over stdio or HTTP/SSE |
| `agentflight benchmark` | Reproduce sub-microsecond throughput metrics on local hardware |

Next guides:
- **[Policy Firewall, Contracts & Forking (`POLICY_AND_CONTRACTS.md`)](POLICY_AND_CONTRACTS.md)**
- **[Copy-Paste Cookbook (`COOKBOOK.md`)](COOKBOOK.md)**
- **[MCP Server & AI Coding Agents Setup (`MCP_AND_AGENTS.md`)](MCP_AND_AGENTS.md)**
