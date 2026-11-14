# MCP Server & AI Coding Agents Setup (`v1.5.0`)

AgentFlight exposes Model Context Protocol (`2024-11-05`) tools, resources, and prompts over **stdio** (`agentflight serve-mcp`) and **Streamable HTTP** (`https://agentflight-tau.vercel.app/mcp`).

---

## 1. Quick Connect via Hosted Streamable HTTP

Stateless public MCP endpoint exposing `agentflight_lint_tools` and `agentflight://rules/catalog`:

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

### Tools (`tools/list`)
- `agentflight_lint_tools` *(Public HTTP + Stdio)* — Static `TS001`–`TS010` schema ergonomics grader.
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
