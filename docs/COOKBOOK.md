# AgentFlight Cookbook — Copy-Paste Production Recipes (`v1.6.0`)

Short, production-ready recipes you can paste straight into Python apps, pytest suites, MCP servers, and GitHub Actions.

---

## Recipe 1: Protect Live OpenAI / Anthropic Calls in 5 Lines

Stop infinite loops, runaway dollar spend, SSRF URLs, and raw secret leaks **before** they happen, while saving a clean commit-safe cassette:

```python
from openai import OpenAI
from agentflight import (
    TrajectoryCircuitBreaker,
    TrajectoryPolicyEngine,
    wrap_openai,
)

guard = TrajectoryCircuitBreaker(
    max_identical_repeats=3,
    max_ping_pong_cycles=2,
    max_cost_usd=0.25,
    policy=TrajectoryPolicyEngine(mode="strict", max_mutations=3),
)

client = wrap_openai(OpenAI(), guard=guard)
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Diagnose API latency"}],
)

# API keys & Bearer tokens are scrubbed BEFORE SHA-256 chain hashing
client.agentflight_recorder.save("tests/cassettes/diagnose.flight.json")
```

For Anthropic Claude (including `stream=True`):

```python
from anthropic import Anthropic
from agentflight import wrap_anthropic, TrajectoryCircuitBreaker

client = wrap_anthropic(Anthropic(), guard=TrajectoryCircuitBreaker(max_cost_usd=0.25))
```

---

## Recipe 2: `$0.00` Deterministic Pytest + Behavioral Contract

Record once when the cassette is missing (`--flight-mode=auto`), then replay offline in `<0.02 ms` in every CI run while asserting behavioral SLAs:

```python
import pytest
from agentflight import FlightContract

@pytest.mark.flight_cassette("tests/cassettes/checkout.flight.json")
def test_checkout_flow(flight_session):
    inventory = flight_session.stub("check_inventory", fallback_fn=lambda sku: {"in_stock": True, "sku": sku})
    charge = flight_session.stub("charge_customer", fallback_fn=lambda sku, cents: {"paid": cents})

    stock = inventory(sku="SKU-42")
    assert stock["in_stock"] is True
    receipt = charge(sku="SKU-42", cents=1900)
    assert receipt["paid"] == 1900

    report = flight_session.assert_contract(
        FlightContract("checkout-sla")
        .must_call("check_inventory", max_calls=1)
        .must_follow_order(["check_inventory", "charge_customer"])
        .must_not_call("refund_all")
        .max_cost_usd(0.05)
        .zero_errors()
        .require_valid_hash_chain()
    )
    assert report.passed, report.summary()
```

Run in CI with network disabled:

```bash
pytest -v --flight-mode=replay
```

---

## Recipe 3: All-in-One GitHub Actions AI Reliability Gate

Lint MCP tool schemas, verify SHA-256 cassette tamper integrity, audit `PF001`–`PF007` safety policies, enforce `FlightContract` SLAs, and post a Markdown summary to your PR:

```yaml
name: AgentFlight Reliability Gate
on: [pull_request]

jobs:
  agent-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install agentflight-mcp pytest
      - run: pytest --flight-mode=replay
      - name: Run AgentFlight Pre-Flight Gate
        run: |
          agentflight ci \
            --schema-file tools.json \
            --cassette tests/cassettes/checkout.flight.json \
            --contract contracts/checkout.contract.json \
            --policy-mode strict \
            --max-cost 0.25 \
            --fail-on-smell \
            --github-summary
```

---

## Recipe 4: Counterfactual Bug-Fix via Time-Travel Forking

Debug step `k` of a failed multi-step agent trajectory without re-paying for upstream steps `0 .. k-1`:

```bash
# 1. Inspect why the original run failed
agentflight post-mortem cassettes/incident.flight.json --output POST_MORTEM.md

# 2. Fork at step 2 with a simulated patched tool response
agentflight replay cassettes/incident.flight.json \
  --fork-at 2 \
  --override-output-json '{"status":"ok","records":[{"id":"fix-1"}]}' \
  --fork-out cassettes/patched.flight.json

# 3. Diff behavioral improvement & verify contract
agentflight diff cassettes/incident.flight.json cassettes/patched.flight.json --json
agentflight contract cassettes/patched.flight.json --must-call close_incident --zero-errors
```

---

## Recipe 5: Auto-Hardening Messy MCP Tool Schemas (`31/100` -> `100/100`)

Fix missing parameter descriptions, unconstrained string enums, ambiguous booleans, and missing `confirm` flags on destructive tools in one command:

```bash
agentflight lint --schema-file raw_tools.json
agentflight fix raw_tools.json --output hardened_tools.json
agentflight lint --schema-file hardened_tools.json
```

Or in Python:

```python
from agentflight import ToolSmellLinter, ToolSchemaOptimizer, SHOWCASE_FLAWED_MCP_TOOLS

optimizer = ToolSchemaOptimizer()
hardened = [res.hardened_tool for res in optimizer.optimize_tools(SHOWCASE_FLAWED_MCP_TOOLS)]
report = ToolSmellLinter().lint(hardened)
print(f"Score: {report.ergonomics_score}/100 (Grade {report.grade})")
```

---

## Recipe 6: Export W3C TraceContext / OpenTelemetry Spans for StackPulse / Jaeger

```bash
agentflight export-otel cassettes/incident.flight.json \
  --service-name checkout-agent \
  --output spans.json
```

```python
from agentflight import export_cassette_to_otel

spans = export_cassette_to_otel(
    "cassettes/incident.flight.json",
    service_name="checkout-agent",
    output_path="spans.json",
)
```
