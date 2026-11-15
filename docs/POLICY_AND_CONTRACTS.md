# Safety Policy Firewall, Behavioral Contracts & Time-Travel Forking (`v1.6.0`)

> **Test interactively in your browser:** Try every firewall preset and contract check in the **[Policy & Contracts Studio](https://codesphere-u.github.io/agentflight/studio.html)** or browse all 22 rules in the **[Rules Reference](https://codesphere-u.github.io/agentflight/rules.html)**.

AgentFlight `v1.6.0` adds three production-safety superpowers on top of the SHA-256 Flight Recorder:

1. **Runtime Policy Firewall (`PF001`–`PF007`)** — Blocks SSRF, path traversal, destructive SQL, unredacted secret leaks, and unauthorized mutations **before a tool ever runs**.
2. **Behavioral Trajectory Contracts (`FlightContract`)** — Declarative CI assertions over required tools, execution order, latency, token spend, and chain integrity.
3. **Time-Travel Cassette Forking (`fork_from` / `fork_at`)** — Branch any recorded trajectory at step `k` with counterfactual tool outputs at **`$0.00` prefix cost**.

---

## 1. Runtime Policy Firewall (`TrajectoryPolicyEngine`)

While `TrajectoryCircuitBreaker` (`CB001`–`CB005`) stops **loops and runaway spend**, `TrajectoryPolicyEngine` (`PF001`–`PF007`) stops **dangerous or out-of-policy tool payloads**.

### Policy Modes

| Mode | Behavior | Best For |
| :--- | :--- | :--- |
| `strict` | Blocks SSRF, traversal, SQL DDL, secrets, blocklists, and enforces mutation limits | Production autonomous agents |
| `read-only` | Blocks **all** mutating/destructive tools (`PF002`) plus security rules | Read-only support/triage copilots |
| `standard` | Enforces security checks (`PF001`, `PF003`–`PF007`) with `warn`/`block` defaults | Staging & integration suites |
| `permissive` | Records violations in `PolicyAuditReport` without raising `PolicyViolationError` | Shadow-mode rollouts |

### Built-In Firewall Rules (`PF001`–`PF007`)

| Rule ID | Guardrail | Example Blocked Payload / Trigger |
| :--- | :--- | :--- |
| **`PF001`** | Tool Allowlist / Blocklist | Calling `exec_shell` when `blocked_actors=["exec_shell"]` or not in `allowed_actors` |
| **`PF002`** | Read-Only & Destructive Gate | Calling `delete_*` / `drop_*` / `write_*` in `read-only` mode |
| **`PF003`** | SSRF & Cloud Metadata Guard | `http://169.254.169.254/latest/meta-data/`, `http://127.0.0.1:8080/admin`, private RFC1918 IPs |
| **`PF004`** | Path Traversal Guard | `../../../../etc/passwd`, `~/.ssh/id_rsa`, `/proc/self/environ` |
| **`PF005`** | Destructive SQL Guard | `DROP TABLE users;`, `TRUNCATE invoices;`, unguarded `DELETE FROM accounts;` |
| **`PF006`** | Unredacted Secret Exfiltration | Outbound payloads containing raw `sk-...`, `sk-ant-...`, `ghp_...`, `AKIA...`, Bearer tokens, JWTs |
| **`PF007`** | Per-Flight Mutation Ceiling | Exceeding `max_mutations=3` mutating calls in a single trajectory |

### Blocking Unsafe Calls Pre-Execution

Pass `policy=...` directly into `TrajectoryCircuitBreaker` — every `guard.observe(...)` (and every wrapped `OpenAI` / `Anthropic` / tool call) runs the firewall first:

```python
from agentflight import (
    TrajectoryCircuitBreaker,
    TrajectoryPolicyEngine,
    PolicyViolationError,
)

policy = TrajectoryPolicyEngine(
    mode="strict",
    allowed_actors=["search_logs", "fetch_url", "query_db"],
    max_mutations=2,
)
guard = TrajectoryCircuitBreaker(max_cost_usd=0.50, policy=policy)

# Allowed call
guard.observe("search_logs", {"service": "checkout", "window": "15m"})

# Blocked BEFORE execution with PolicyViolationError (PF003)
try:
    guard.observe("fetch_url", {"url": "http://169.254.169.254/latest/meta-data/"})
except PolicyViolationError as exc:
    print(exc.rule_id, exc.message)
    # -> PF003 Blocked internal/cloud-metadata URL (169.254.169.254)
```

### Writing Custom Policy Rules (`add_rule`)

```python
engine = TrajectoryPolicyEngine(mode="strict")
engine.add_rule(
    rule_id="ORG001",
    description="Require ticket_id when updating production records",
    predicate=lambda actor, payload: not (
        actor.startswith("update_") and not (payload or {}).get("ticket_id")
    ),
    severity="block",
)
```

### Offline Cassette Auditing (`CLI` & Python)

```bash
agentflight policy-audit runs/prod_incident.flight.json --mode read-only --json
```

```python
report = TrajectoryPolicyEngine(mode="strict").audit_cassette("runs/prod_incident.flight.json")
assert report.passed, [v.to_dict() for v in report.violations]
```

---

## 2. Behavioral Trajectory Contracts (`FlightContract`)

Checking final text with regexes misses silent tool-use bugs. **`FlightContract`** lets you express clear behavioral SLAs over *which tools ran*, *in what order*, *at what cost/latency*, and *without secret leaks or hash tampering*.

### Fluent Builder Example

```python
from agentflight import FlightContract, assert_trajectory

contract = (
    FlightContract("checkout-sla")
    .must_call("verify_inventory", min_calls=1, max_calls=2)
    .must_not_call("drop_database")
    .must_follow_order(["verify_inventory", "charge_card", "send_receipt"])
    .max_steps(8)
    .max_cost_usd(0.15)
    .max_tokens(12_000)
    .max_total_latency_ms(5_000.0)
    .zero_errors()
    .require_valid_hash_chain()
    .require_no_secret_leaks()
)

report = assert_trajectory("tests/cassettes/checkout.flight.json", contract)
assert report.passed, report.summary()
```

### Pytest Integration (`flight_session.assert_contract`)

```python
import pytest
from agentflight import FlightContract

@pytest.mark.flight_cassette("tests/cassettes/triage.flight.json")
def test_triage_meets_contract(flight_session):
    search = flight_session.stub("search_logs", fallback_fn=lambda q: {"hits": [q]})
    summarize = flight_session.stub("summarize_incident", fallback_fn=lambda hits: {"ok": True})

    hits = search(q="502 timeout")
    summarize(hits=hits)

    report = flight_session.assert_contract(
        FlightContract("triage-sla")
        .must_call("search_logs")
        .must_follow_order(["search_logs", "summarize_incident"])
        .max_cost_usd(0.10)
        .zero_errors()
    )
    assert report.passed
```

### JSON Contract & CI Gate

Save reusable SLA specs in `contracts/prod.contract.json`:

```json
{
  "name": "sre-triage-sla",
  "must_call": ["search_logs", "summarize_incident"],
  "must_not_call": ["exec_shell", "drop_table"],
  "must_follow_order": ["search_logs", "summarize_incident"],
  "max_steps": 10,
  "max_cost_usd": 0.25,
  "zero_errors": true,
  "require_valid_hash_chain": true,
  "require_no_secret_leaks": true
}
```

Run standalone or inside your GitHub Actions `agentflight ci` gate:

```bash
agentflight contract tests/cassettes/triage.flight.json --contract-file contracts/prod.contract.json --json
agentflight ci --schema-file tools.json --cassette tests/cassettes/triage.flight.json \
  --contract contracts/prod.contract.json --policy-mode strict --fail-on-smell --github-summary
```

---

## 3. Time-Travel Cassette Forking (`fork_from` / `fork_at`)

When step 4 of a 12-step trajectory fails because a tool returned an unexpected error or schema, you shouldn't have to pay for steps 0–3 over and over while iterating.

**Time-Travel Forking** copies steps `0 .. up_to_step`, optionally patches step `k`'s `output_payload` / `status`, recomputes canonical SHA-256 hashes from `GENESIS_HASH`, and gives you a fresh `FlightRecorder` ready to continue running or diffing against the original flight.

```python
from agentflight import CassetteReplayer, compare_cassettes, verify_cassette

replayer = CassetteReplayer("cassettes/failed_run.flight.json")

# Branch at step 2 with a counterfactual output override ($0.00 prefix replay!)
forked = replayer.fork_at(
    step_index=2,
    agent_id="sre-agent-counterfactual",
    override_output={"status": "200 OK", "latency_p99_ms": 42.0},
    override_status="ok",
)

# Record new continuation steps on top of the patched branch
forked.record(
    kind="tool_call",
    actor="close_incident",
    input_payload={"incident_id": "INC-8841"},
    output_payload={"closed": True},
    cost_usd=0.001,
)
forked.save("cassettes/fixed_branch.flight.json")

assert verify_cassette(forked) is True
diff = compare_cassettes("cassettes/failed_run.flight.json", "cassettes/fixed_branch.flight.json")
print(diff.summary_markdown)
```

Or via the CLI:

```bash
agentflight replay cassettes/failed_run.flight.json \
  --fork-at 2 \
  --override-output-json '{"status":"200 OK","patched":true}' \
  --fork-out cassettes/fixed_branch.flight.json
```
