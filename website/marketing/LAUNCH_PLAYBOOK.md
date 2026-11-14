# AgentFlight v1.5.0 Launch Playbook

## Positioning

- **Headline:** Record, replay, and guard every agent turn.
- **Audience:** AI agent engineers, MCP server authors, and QA/CI teams fighting flaky non-deterministic LLM test runs and runaway token loops.
- **Core Proof:** `0.08 us` replay per span, `$0.00` CI spend, canonical SHA-256 chain with automatic secret scrubbing, `10` static MCP tool-smell rules, `167+` unit tests (`>90%` coverage), pure stdlib core.

## Distribution Channels

1. **GitHub Pages Docs & Interactive Studio (`https://codesphere-u.github.io/agentflight/`)**: Live browser linter, circuit breaker simulator, and multi-page documentation.
2. **PyPI (`agentflight-mcp`)**: `pip install agentflight-mcp` or `uvx --from agentflight-mcp agentflight doctor`.
3. **MCP Registries (Glama & Smithery)**: `https://agentflight-tau.vercel.app/mcp` Streamable HTTP and stdio bundles.
4. **Developer Content**: Compare AgentFlight `.flight.json` cassettes against live CI test spend and ad-hoc `unittest.mock` fixtures.
