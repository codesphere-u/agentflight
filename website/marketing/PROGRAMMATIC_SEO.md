# AgentFlight Programmatic SEO & GEO Strategy

## High-Intent Content Clusters

1. **Comparison Pages**:
   - `/compare/vcrpy-vs-agentflight-for-mcp-agents` — Multi-step JSON-RPC MCP tool stubbing + SHA-256 tamper protection.
   - `/compare/live-llm-ci-vs-cassette-replay` — Eliminating 30s live API flakes and overnight CI spend.
2. **MCP Ergonomics Rules Reference (`TS001`–`TS010`)**:
   - Dedicated anchorable guides covering ambiguous boolean flags (`TS005`), unconstrained enums (`TS006`), tool name cosine collisions (`TS008`), and destructive tool safety guards (`TS010`).
3. **Framework Integration Guides**:
   - OpenAI Responses & Chat streaming cassette recording (`wrap_openai`)
   - Anthropic Messages streaming & tool-use capture (`wrap_anthropic`)
   - Auto-registered pytest fixtures (`@pytest.mark.flight_cassette`)
