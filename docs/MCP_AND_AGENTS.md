# MCP Server & AI Coding Agents Setup (`v1.6.0`)

AgentFlight exposes **8 Model Context Protocol (`2024-11-05`) tools**, **2 JSON resources**, and **2 diagnostic prompts** over **stdio** (`agentflight serve-mcp`), **standalone HTTP/SSE** (`agentflight serve-http`), and our **public hosted Vercel endpoint** (`https://agentflight-tau.vercel.app/mcp`).

---

## 1. Quick Connect via Hosted Streamable HTTP (Zero Install)

The stateless public endpoint exposes **5 hosted tools** (`agentflight_lint_tools`, `agentflight_optimize_tools`, `agentflight_post_mortem`, `agentflight_audit_policy`, `agentflight_evaluate_contract` via inline `cassette_json`), plus resources and prompts:

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

Or via Smithery:

```bash
npx -y @smithery/cli install @codesphere-u/agentflight --client claude
```

---

## 2. Local Stdio Mode (`uvx`) — Full Local File Access (All 8 Tools)

Use local stdio mode whenever agents inspect `.flight.json` files on disk (`agentflight_verify_cassette`, `agentflight_diff_cassettes`, `agentflight_export_otel`, or passing `cassette_path` to post-mortem/policy/contract tools):

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

Test locally via CLI:

```bash
uvx --from agentflight-mcp agentflight doctor
agentflight serve-mcp
```

---

## 3. All Exposed MCP Primitives

### Tools (`tools/list` — 8 Tools)

| Tool | Transport | Purpose |
| :--- | :--- | :--- |
| `agentflight_lint_tools` | Hosted HTTP + Stdio | Static `TS001`–`TS010` schema ergonomics audit & score (`0–100`) |
| `agentflight_optimize_tools` | Hosted HTTP + Stdio | Rewrites weak MCP schemas to high-ergonomics Gold Standard |
| `agentflight_post_mortem` | Hosted HTTP (`cassette_json`) + Stdio | AAIB/NTSB root-cause Markdown + JSON incident report |
| `agentflight_audit_policy` | Hosted HTTP (`cassette_json` / inline call) + Stdio | Audits single calls or trajectories against `PF001`–`PF007` |
| `agentflight_evaluate_contract` | Hosted HTTP (`cassette_json`) + Stdio | Evaluates declarative `FlightContract` assertions & cost caps |
| `agentflight_verify_cassette` | Local Stdio / Self-Hosted | Canonical SHA-256 hash-chain tamper verification on local files |
| `agentflight_diff_cassettes` | Local Stdio / Self-Hosted | Baseline vs. candidate Levenshtein/LCS sequence and cost diff |
| `agentflight_export_otel` | Local Stdio / Self-Hosted | Exports W3C TraceContext OpenTelemetry JSON spans |

> **Hosted Security Isolation:** On the shared Vercel gateway (`api/index.py`), local filesystem tools (`agentflight_verify_cassette`, `agentflight_diff_cassettes`, `agentflight_export_otel`) are blocked, and `cassette_path` is disallowed on hosted `post_mortem`/`audit_policy`/`evaluate_contract` calls — pass inline `cassette_json` instead.

### Resources (`resources/list`, `resources/read`)
- `agentflight://rules/catalog` — Full JSON specification of `TS001`–`TS010` ergonomics rules.
- `agentflight://metrics/summary` — Sub-millisecond replay and linter throughput metrics.

### Prompts (`prompts/list`, `prompts/get`)
- `lint-tool-definitions` — Audits and refactors flawed MCP schemas.
- `review-agent-trajectory` — Guides an LLM through incident root-cause triage.

---

## 4. JSON-RPC Examples (Works Directly on Hosted `/mcp`)

### Audit a Single Tool Call Against `PF001`–`PF007`

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "agentflight_audit_policy",
    "arguments": {
      "mode": "strict",
      "actor": "fetch_url",
      "input_payload": { "url": "http://169.254.169.254/latest/meta-data/" }
    }
  }
}
```

### Evaluate a Inline Cassette Against a Behavioral Contract

```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "method": "tools/call",
  "params": {
    "name": "agentflight_evaluate_contract",
    "arguments": {
      "cassette_json": {
        "agent_id": "checkout-agent",
        "spans": [
          {
            "step_index": 0,
            "kind": "tool_call",
            "actor": "search_logs",
            "input_payload": {"q": "502"},
            "output_payload": {"hits": 3},
            "status": "ok",
            "cost_usd": 0.002
          }
        ]
      },
      "contract": {
        "name": "ci-sla",
        "must_call": ["search_logs"],
        "must_not_call": ["drop_database"],
        "max_cost_usd": 0.1,
        "zero_errors": true
      }
    }
  }
}
```
