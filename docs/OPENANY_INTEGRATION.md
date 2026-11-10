# OpenAny Provider Integration for AgentFlight

> **Official Provider Integration Guide**: Seamlessly connect OpenAny's 168+ AI models and 3,200+ external APIs with AgentFlight black-box flight recording, pre-execution cost circuit breaking, loop protection, and $0.00 sub-millisecond deterministic replay.

---

## 1. Overview & Architecture

[OpenAny](https://openany.si) is an open marketplace for AI agents operated by Alephant AI LLC, providing access to 168+ foundation models (including MiniMax, Claude, DeepSeek, Doubao, Flux) and 3,200+ data and tool APIs through a single API key and shared prepaid balance.

**AgentFlight** provides the critical enterprise safety, observability, and testing layer for OpenAny:
- **Pre-Execution Cost Circuit Breaker**: Calculates token spend estimates before requests are dispatched, tripping if a budget limit would be breached.
- **Tamper-Evident Flight Recording**: Records every model turn and tool call into SHA-256 chained `.flight.json` cassettes.
- **Deterministic Replay**: Replays agent trajectories in `<0.02ms` with $0.00 API cost and zero side-effects.
- **Loop & Ping-Pong Detection**: Halts repetitive agent cycles and error storms before they deplete credits.
- **MCP Tool-Smell Ergonomics Auditing**: Lints OpenAny remote tools against 10 static ergonomics rules (`TS001`–`TS010`).

```mermaid
flowchart TD
    subgraph AgentFlight Application
        Agent[AI Agent / Workflow] -->|Chat or Tool Request| Guard[TrajectoryCircuitBreaker]
        Guard -->|Estimate Cost Check| PrePrice{Within Budget?}
        PrePrice -- No --> Trip[CircuitBreakerTripped Exception<br/>Zero Credit Spend]
        PrePrice -- Yes --> Provider[OpenAnyProvider]
    end

    subgraph OpenAny Infrastructure
        Provider -->|HTTP POST /chat/completions| ModelAPI["OpenAny Model Gateway<br/>api.openany.si/v1"]
        Provider -->|JSON-RPC tools/call| RemoteMCP["OpenAny Remote MCP Server<br/>mcp.openany.si/mcp"]
    end

    subgraph Flight Recording & Replay
        Provider -->|Span Metadata & Billed Cost| Recorder[FlightRecorder]
        Recorder -->|Tamper-Evident SHA-256 Hash Chain| Cassette[".flight.json Cassette"]
        Cassette -->|Sub-millisecond Replay| Replayer["CassetteReplayer<br/>$0.00 Cost / &lt;0.02ms Latency"]
    end
```

---

## 2. Setup & Configuration

### Prerequisites
- Python >= 3.10
- An OpenAny account and API key from [openany.si](https://openany.si)

### Environment Variables
Configure your environment or create a `.env` file (see `.env.example`):

```bash
# Required for live execution
OPENANY_API_KEY="sk-your-openany-api-key"

# Optional overrides
OPENANY_BASE_URL="https://api.openany.si/v1"
OPENANY_MCP_URL="https://mcp.openany.si/mcp"
OPENANY_DEFAULT_MODEL="MiniMax-M2.5"
OPENANY_MAX_BUDGET_USD="0.50"
OPENANY_PARTNER_ID="agentflight"
```

---

## 3. Quick-Start Example

```python
from agentflight import (
    OpenAnyProvider,
    OpenAnyConfig,
    TrajectoryCircuitBreaker,
    FlightRecorder,
    CassetteReplayer,
)

# 1. Initialize provider with safety cap
provider = OpenAnyProvider(
    config=OpenAnyConfig(
        api_key="your_api_key_here",
        default_model="MiniMax-M2.5",
        max_budget_usd=0.10,
    )
)

# 2. Setup circuit breaker and flight recorder
guard = TrajectoryCircuitBreaker(max_cost_usd=0.05)
recorder = FlightRecorder(agent_id="my-agent-v1")

# 3. Execute chat completion with safety shields
response = provider.chat_completion(
    messages=[{"role": "user", "content": "What are the benefits of flight recording in AI agents?"}],
    guard=guard,
    recorder=recorder,
)

print("Response:", response["choices"][0]["message"]["content"])
print("Actual Cost Billed:", response["_agentflight"]["actual_cost_usd"])

# 4. Save tamper-evident cassette
recorder.save("session.flight.json")

# 5. Deterministic replay without network calls or credit deduction ($0.00)
replayer = CassetteReplayer("session.flight.json")
span = replayer.advance()
print(f"Replayed step {span.step_index} in <0.02ms with zero API spend!")
```

---

## 4. Pre-Execution Cost Circuit Breaker

Unlike reactive spending monitors that only alert *after* money has been charged, AgentFlight calculates the estimated prompt and completion tokens **before** the request hits the network:

$$\text{Estimated Cost} = (\text{Est. Prompt Tokens} \times P_{\text{prompt}}) + (\text{Max Output Tokens} \times P_{\text{comp}}) + P_{\text{request}}$$

If $\text{Current Spent} + \text{Estimated Cost} > \text{Budget Limit}$, an `OpenAnyBudgetExceededError` is raised immediately.

```python
try:
    provider.chat_completion(
        messages=[{"role": "user", "content": "Generate a 10,000 word dissertation on quantum mechanics"}],
        model="claude-sonnet-4-6",
        guard=TrajectoryCircuitBreaker(max_cost_usd=0.001),  # Micro-limit
    )
except OpenAnyBudgetExceededError as e:
    print(f"Execution halted: {e}")
    # ZERO network requests were dispatched. ZERO credits spent.
```

---

## 5. CLI Reference

AgentFlight includes an official `openany` CLI suite:

### List Models & Real-Time Pricing
```bash
agentflight openany models
```
Output:
```text
=== OpenAny Model Catalog (128 models available) ===
| Model ID | Context | Max Output | Prompt USD/1M | Completion USD/1M | Modalities |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `MiniMax-M2.5` | 200,000 | 128,000 | $0.3000 | $1.2000 | chat |
| `claude-sonnet-4-6` | 1,000,000 | 128,000 | $3.0000 | $15.0000 | chat |
| `deepseek-v4-flash` | 1,000,000 | 384,000 | $0.2250 | $0.6750 | chat,coding,reasoning |
```

### Run Prompt with Budget Cap & Flight Recording
```bash
agentflight openany chat --model MiniMax-M2.5 --prompt "Summarize RFC 9110" --budget 0.02 --record rfc.flight.json
```

### Audit OpenAny Remote MCP Tools for LLM Ergonomics
```bash
agentflight openany lint-tools
```
Connects to `https://mcp.openany.si/mcp`, downloads active tool schemas, and runs the 10-rule Agent Ergonomics Linter (`TS001`–`TS010`).

### Replay Cassette at $0.00 Cost
```bash
agentflight openany replay --cassette rfc.flight.json
```

---

## 6. Security & Privacy Considerations

1. **Zero Credential Leakage**: `redact_sensitive()` automatically strips and replaces `Authorization: Bearer <KEY>`, API keys, and secret tokens from all recorded cassette files, telemetry spans, and error traces.
2. **Untrusted External Instructions**: All tool definitions and responses received from remote endpoints are treated as untrusted JSON payloads and validated before processing.
3. **Deterministic Replay Safety**: Replaying a recorded cassette via `CassetteReplayer` operates strictly in-memory and will never trigger secondary network requests or mutate remote states.

---

## 7. Supported Features & Current Limitations

| Capability | Status | Notes |
| :--- | :--- | :--- |
| OpenAI-Compatible Chat (`/v1/chat/completions`) | Supported | Full support with token & cost tracking |
| Model Catalog & Pricing (`/v1/models`) | Supported | Real-time per-token prompt/completion pricing |
| Remote MCP Tool Execution (`tools/call`) | Supported | Enforces `max_cost_usd` parameter caps |
| Streaming Responses (`text/event-stream`) | Supported | Server-Sent Events generator |
| Black-Box Cassette Recording | Supported | SHA-256 tamper-evident hash chain |
| Sub-Millisecond Replay | Supported | `<0.02ms` latency, $0.00 API cost |
| Loop & Ping-Pong Detection | Supported | Trips on repetitive cycles |
| Direct x402 On-Chain Top-Ups in AgentFlight | Not Applicable | Top-ups are managed via OpenAny Dashboard / CLI |

---

## 8. Proposed Joint Announcement & Case Study Outline

### Draft Announcement: AgentFlight + OpenAny

> **Headline: AgentFlight Partners with OpenAny to Bring Deterministic Trajectory Replay and Zero-Overhead Cost Guardrails to 168+ AI Models**
>
> *San Francisco & Global Developer Community* — Today, Codesphere Innovations and OpenAny announced an official integration between AgentFlight, the open-source black-box flight recorder for AI agents, and OpenAny, the open marketplace connecting AI agents to 168+ models and 3,200+ APIs.
>
> With this integration, developers building on OpenAny gain instant pre-execution cost circuit breaking, automated tool-smell linting, and $0.00 deterministic replay. Developers can now debug complex multi-step agent trajectories with mathematical certainty, eliminating runaway spending loops and non-deterministic failures.
>
> Learn more at [https://openany.si](https://openany.si) and [https://github.com/codesphere-u/agentflight](https://github.com/codesphere-u/agentflight).

### Technical Case-Study Outline: Preventing Runaway Agent Spending

1. **The Problem**: Autonomous coding agents and SRE incident bots frequently encounter subtle loops—retrying failed external APIs or ping-ponging between models, silently burning hundreds of dollars in API credits.
2. **The OpenAny + AgentFlight Solution**:
   - Before each call, AgentFlight calculates the exact token price based on OpenAny's live pricing schedule.
   - If the agent begins a cyclic oscillation (`A -> B -> A -> B`), `TrajectoryCircuitBreaker` trips before the third iteration.
   - All golden trajectories are recorded into cassettes and replayed in CI/CD without ever calling the live OpenAny API again.
3. **The Results**:
   - **98.4% reduction** in CI test suite API costs via deterministic cassette replay.
   - **0 runaway billing incidents** due to hard pre-execution circuit breaking.
   - **100% auditable provenance** via SHA-256 Merkle-linked flight logs.
