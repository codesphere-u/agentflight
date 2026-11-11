# AgentFlight × OpenAny — Demonstration Video Shot List (60–90s)

**Target Audience:** AI Agent Developers, Open-Source Engineers, Enterprise AI Teams  
**Format:** Screen recording with aerospace terminal visuals + voiceover + background synth hum  
**Duration:** 75 seconds  
**Script & Direction:** Akandwanaho Ivan Alvin  
**Partner Integration:** OpenAny (`X-OpenAny-Partner-Id: agentflight`)  

---

## Shot Overview

| Scene | Timestamp | Visual Composition | Voiceover Script (Audio) |
| :--- | :--- | :--- | :--- |
| **01** | `00:00 - 00:08` | Title card: Aerospace cockpit layout with electric blue (`#0047ff`) and radar amber (`#f59e0b`). Text: "AgentFlight × OpenAny: Commercial Integration". | *"What happens when the fastest AI flight recorder meets an open marketplace of 128+ models and 3,200 APIs? Total reliability."* |
| **02** | `00:08 - 00:18` | Terminal split: CLI running `agentflight openany models`. Live model matrix cascading on screen showing pricing per 1M tokens. | *"With AgentFlight v1.2, connect to OpenAny with zero friction. Query live models, context windows, and real-time per-token pricing directly from your terminal."* |
| **03** | `00:18 - 00:30` | Wireshark/HTTP inspection overlay showing `POST https://api.openany.si/v1/chat/completions` with highlighted header: `X-OpenAny-Partner-Id: agentflight`. | *"Every request transmits our verified partner attribution header, powering permanent revenue sharing while strictly isolating credentials from external domains."* |
| **04** | `00:30 - 00:44` | High-tension animation: Agent tries to dispatch an expensive 50k prompt with strict `$0.001` budget cap. Neon red HUD alert: `[CIRCUIT BREAKER TRIPPED BEFORE EXECUTION]`. | *"Never burn through your prepaid credits again. AgentFlight's pre-execution circuit breaker calculates costs before dispatch and halts unaffordable calls before they leave your machine."* |
| **05** | `00:44 - 00:54` | Terminal: Agent enters ping-pong tool loop. Circuit breaker detects `exact_call_loop` at step 2 and safely halts execution. | *"Runaway agent loops and infinite retry storms are halted instantly. Your spend is protected; your models stay focused."* |
| **06** | `00:54 - 01:05` | Hex-editor & JSON viewer showing `.flight.json` cassette with SHA-256 hash chain and redacted API keys. CLI runs `agentflight openany replay`. | *"Every step is black-box recorded into an immutable, tamper-evident cassette. Replay entire trajectories in microseconds—completely offline, with zero network calls and zero cost."* |
| **07** | `01:05 - 01:15` | Terminal running `agentflight openany lint-tools`. Score card showing 10 tool ergonomics rules (TS001-TS010) optimizing 28,000 token schemas down to high-density payloads. | *"Audit OpenAny remote MCP tools with our static linter. Detect untyped properties, eliminate prompt bloat, and maximize function-calling accuracy."* |
| **08** | `01:15 - 01:25` | Final splash screen: GitHub repo link, Vercel portal URL (`agentflight-tau.vercel.app`), OpenAny logo. Text: "Created & Owned by Akandwanaho Ivan Alvin. Partnered with OpenAny." | *"AgentFlight: The black-box telemetry and cost control plane for the agentic web. Available now on GitHub and pip."* |

---

## Technical Setup Instructions for Screen Recording

1. **Terminal Profile:**
   - Font: `JetBrains Mono` or `Fira Code`, size 16pt.
   - Background: Pitch black `#06080d`.
   - Foreground: Clean white `#f1f5f9`, electric blue `#0047ff`, radar amber `#f59e0b`.
2. **Execution Command:**
   ```bash
   ./scripts/demo_openany_commercial.py
   ```
3. **Key Safety Reminder:**
   - Verify that the terminal output displays `ale-P4...7ydY` (redacted), never the raw API key.
