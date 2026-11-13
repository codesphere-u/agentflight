# AgentFlight v1.2.0 — Commercial OpenAny Integration & Thread-Safe Budget Reservation

**Release Tag:** `v1.2.0`  
**Date:** November 11, 2026  
**Author & Owner:** Akandwanaho Ivan Alvin  

---

## What's Changed in v1.2.0

AgentFlight v1.2.0 introduces the official commercial integration with **OpenAny**, accompanied by production-grade revenue attribution, thread-safe concurrent budget reservations, streaming SSE support, and remote MCP tool auditing.

### 🌟 Key Highlights

1. **Commercial Attribution Infrastructure:**
   - Outbound requests to OpenAny now transmit the confirmed attribution header:
     ```http
     X-OpenAny-Partner-Id: agentflight
     ```
   - Powers a permanent 30% revenue sharing partnership with OpenAny.
   - Domain boundary isolation strictly prevents header and credential leakage to third-party domains.

2. **Thread-Safe Budget Reservations (`TrajectoryCircuitBreaker`):**
   - Added `guard.reserve_budget(amount_usd)` with `BudgetReservation` context manager.
   - Prevents race conditions in multi-threaded and concurrent agent runs from bypassing spending caps before completion.
   - Pre-execution budget evaluations halt unaffordable requests before network dispatch ($0.00 spent).

3. **Streaming Chat Completions (`stream_chat`):**
   - Added generator support for real-time Server-Sent Events (SSE) streaming.
   - Live chunk delivery with post-stream token reconciliation and span recording.

4. **Remote MCP Tool-Smell Auditing:**
   - Query and lint remote OpenAny MCP servers (`https://mcp.openany.si/mcp`).
   - Audit schemas against rules TS001–TS010 to trim prompt bloat by up to 78%.

5. **Sub-Microsecond Deterministic Replay Benchmark:**
   - Benchmarked at **0.08 μs per span** (>11,000,000 spans/sec) across 25,000 span trials.
   - 100% offline with zero external network calls.

6. **Refined Secret Redaction:**
   - Intelligent masking protects sensitive keys and bearer tokens while preserving numerical metric tokens (`prompt_tokens`, `completion_tokens`, `total_tokens`).

### 📦 Installation
```bash
pip install --upgrade agentflight-mcp
```

### 🧪 Full Test Suite Status
- **132 passed**, 1 skipped in 3.88s (100% passing across mock and live test fixtures).
- 20 dedicated provider and attribution tests.
