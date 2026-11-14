# Getting Started with AgentFlight (`v1.5.0`)

Welcome to **AgentFlight** — an open-source black-box flight recorder, deterministic `$0.00` CI trajectory replayer, loop/budget circuit breaker, and 10-rule MCP tool-smell linter.

> Browse the interactive version with copy buttons and live sandbox tools at **`https://codesphere-u.github.io/agentflight/docs.html`**.

---

## Choose Your Path

### 1. AI Application Engineers (Wrap Live SDK Calls in 1 Line)

Install from PyPI (`pip install agentflight-mcp`; Python import stays `import agentflight`):

```bash
pip install agentflight-mcp
agentflight doctor --json
```

Wrap `OpenAI`, `AsyncOpenAI`, OpenRouter, vLLM, or `Anthropic` clients with a runtime loop and spend ceiling:

```python
from openai import OpenAI
from agentflight import wrap_openai, TrajectoryCircuitBreaker

client = wrap_openai(OpenAI(), guard=TrajectoryCircuitBreaker(max_cost_usd=0.25))
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Check service health"}],
)
client.agentflight_recorder.save("tests/cassettes/health.flight.json")
```

API keys (`sk-...`, `ghp_...`, Bearer tokens, JWTs) are scrubbed **before** computing SHA-256 chain hashes, so saved `.flight.json` cassettes are safe to commit.

---

### 2. QA & CI Engineers (Zero-Cost Deterministic Pytest Replay)

Installing `agentflight-mcp` automatically activates the `pytest11` plugin (`flight_recorder`, `flight_guard`, `flight_session`, `@pytest.mark.flight_cassette`):

```python
import pytest

@pytest.mark.flight_cassette("tests/cassettes/checkout.flight.json")
def test_checkout_deterministic(flight_session, flight_guard):
    search = flight_session.stub("search_catalog", fallback_fn=lambda q: {"hits": [q]})
    assert search(q="router")["hits"] == ["router"]
```

Run replay checks in CI with zero upstream LLM spend:

```bash
pytest -v --flight-mode=replay
agentflight diff baseline.flight.json candidate.flight.json --similarity-threshold 0.85
```

---

### 3. MCP Server Authors (Lint & Auto-Fix Tool Schemas)

Catch ambiguous boolean flags, missing enums, cosine tool collisions (`TS008`), and unguarded destructive operations (`TS010`) before deployment:

```bash
agentflight lint
agentflight lint --schema-file tools.json --json
agentflight fix tools.json --output hardened_tools.json
```

Test schemas interactively right in your browser at **`https://codesphere-u.github.io/agentflight/studio.html`**.

---

## Core CLI Subcommands

| Command | Purpose |
| :--- | :--- |
| `agentflight doctor [--json]` | Run offline self-diagnostics across core stdlib, pytest plugin, SHA-256 redaction & circuit breaker |
| `agentflight demo` | Replay end-to-end incident trajectory, ping-pong breaker & diff showcase |
| `agentflight lint` | Audit built-in or `--schema-file` MCP definitions across `TS001`–`TS010` |
| `agentflight fix <file>` | Auto-repair smelly MCP schemas to Glama Gold Standard |
| `agentflight ci` | Combined schema + cassette integrity + budget SLA gate with optional `$GITHUB_STEP_SUMMARY` |
| `agentflight post-mortem <cassette>` | Generate AAIB/NTSB incident report pinpointing loops or cost spikes |
| `agentflight export-otel <cassette>` | Export W3C TraceContext spans for StackPulse, Jaeger, or Datadog |
| `agentflight benchmark` | Reproduce Python stdlib throughput metrics on local hardware |
