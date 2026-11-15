# MCP Server & AI Coding Agents Setup (`v1.6.0`)

AgentFlight exposes 8 Model Context Protocol (`2024-11-05`) tools, resources, and prompts over **stdio** (`agentflight serve-mcp`) and **Streamable HTTP** (`https://agentflight-tau.vercel.app/mcp`).

---

## 1. Quick Connect via Hosted Streamable HTTP

Stateless public MCP endpoint exposing `agentflight_lint_tools`, `agentflight_optimize_tools`, `agentflight_post_mortem`, `agentflight_audit_policy`, `agentflight_evaluate_contract`, and `agentflight://rules/catalog` (with `cassette_path` disabled on hosted HTTP — supply inline `cassette_json`):

- **Endpoint:** `https://agentflight-tau.vercel.app/mcp`
- **Health Probe:** `https://agentflight-tau.vercel.app/health`

```bash
claude mcp add --transport http agentflight https://agentflight-tau.vercel.app/mcp
```

For Cursor, Windsurf, or Claude Desktop (`mcp.json`):

```json
{
  "mcpServers": {
    "agentflight": {
      "type": "http",
      "url": "https://agentflight-tau.vercel.app/mcp"
    }
  }
}
```

---

## 2. Local Stdio Mode (`uvx`) — Full Cassette File Access

Use stdio mode whenever tools inspect `.flight.json` files on local disk (`agentflight_verify_cassette`, `agentflight_diff_cassettes`, `agentflight_export_otel`):

```json
{
  "mcpServers": {
    "agentflight": {
      "command": "uvx",
      "args": [
        "--from",
        "agentflight-mcp",
        "agentflight",
        "serve-mcp"
      ]
    }
  }
}
```

Or test locally via CLI:

```bash
uvx --from agentflight-mcp agentflight doctor
agentflight serve-mcp
```

---

## 3. Exposed MCP Primitives

### Tools (`tools/list` — 8 Tools)
- `agentflight_lint_tools` *(Public HTTP + Stdio)* — Static `TS001`–`TS010` schema ergonomics grader.
- `agentflight_optimize_tools` *(Public HTTP + Stdio)* — Computes concrete schema fixes for weak MCP tools.
- `agentflight_post_mortem` *(Public HTTP + Stdio w/ inline `cassette_json`)* — AAIB/NTSB root-cause Markdown/JSON incident report.
- `agentflight_audit_policy` *(Public HTTP + Stdio w/ inline `cassette_json`)* — Audits trajectories against `PF001`–`PF007` Policy Firewall rules.
- `agentflight_evaluate_contract` *(Public HTTP + Stdio w/ inline `cassette_json`)* — Evaluates declarative `FlightContract` assertions and budgets.
- `agentflight_verify_cassette` *(Local Stdio)* — Canonical SHA-256 hash-chain tamper verification.
- `agentflight_diff_cassettes` *(Local Stdio)* — Baseline vs. candidate Levenshtein/LCS sequence and cost diff.
- `agentflight_export_otel` *(Local Stdio)* — Converts cassettes into W3C TraceContext OpenTelemetry JSON spans.

### Resources & Prompts
- `agentflight://rules/catalog` — Full JSON specification of rules `TS001`–`TS010`.
- `agentflight://metrics/summary` — Sub-millisecond replay and linter throughput metrics.
- Prompts: `lint-tool-definitions`, `review-agent-trajectory`.

---

## 4. GitHub Actions CI Integration

```yaml
- name: Run AgentFlight Pre-Flight Gate
  run: |
    pip install agentflight-mcp
    agentflight ci --schema-file tools.json --cassette tests/cassettes/run.flight.json --fail-on-smell --github-summary
```

Pair with `pytest -v --flight-mode=replay` to block trajectory divergence and runaway token regressions cleanly in every pull request.
