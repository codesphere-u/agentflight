# AgentFlight × OpenAny — Live Revenue Attribution Record

**Status:** `DISPATCHED_AWAITING_BACKEND_CONFIRMATION`  
**Protocol Version:** `v1.2.0`  
**Verification Date:** November 11, 2026 (06:37:00 UTC)  
**AgentFlight Owner:** Akandwanaho Ivan Alvin  
**Commercial Partner:** OpenAny (Founder: Pistis)  
**Attribution Parameter:** `X-OpenAny-Partner-Id: agentflight`  

---

## 1. Executive Summary

This document records the exact telemetry and network payload of an end-to-end controlled live request dispatched through AgentFlight to OpenAny's production API gateway (`https://api.openany.si/v1`).

The request was executed under an explicit strict spending cap of **\$0.01 USD** to verify that:
1. Outbound HTTP requests from AgentFlight carry the exact confirmed partner attribution header:  
   `X-OpenAny-Partner-Id: agentflight`
2. The user-agent is transparently identified as:  
   `agentflight/1.2.0 (partner=openany; https://github.com/codesphere-u/agentflight)`
3. OpenAny's production backend gateway accepts, executes, and responds to the request.
4. Telemetry (tokens, latency, billed cost) is captured in an immutable AgentFlight black-box cassette for auditability.
5. Exact request identifiers are preserved for Pistis to confirm attribution matching in the OpenAny partner accounting database once the partner dashboard is live (expected in 2–3 days).

> [!IMPORTANT]
> In accordance with our commercial readiness guidelines, commercial attribution is **not declared fully verified** until OpenAny confirms that request `0743400fadffb4e5fa37eacbe28eb0fa` has been successfully attributed to `agentflight` on OpenAny's backend ledger.

---

## 2. Dispatch Telemetry

| Parameter | Recorded Value |
| :--- | :--- |
| **Request Timestamp (UTC)** | `2026-11-11T06:37:00.789358+00:00` |
| **Target URL** | `https://api.openany.si/v1/chat/completions` |
| **HTTP Method** | `POST` |
| **Attribution Header** | `X-OpenAny-Partner-Id: agentflight` |
| **User-Agent** | `agentflight/1.2.0 (partner=openany; https://github.com/codesphere-u/agentflight)` |
| **Accept Header** | `application/json, text/event-stream` |
| **Model Requested** | `MiniMax-M2.5` |
| **Prompt Text** | `"Respond with one single word: AgentFlight."` |
| **Temperature** | `0.0` |
| **Max Output Tokens** | `8` |
| **Circuit Breaker Spending Cap** | `\$0.010000 USD` |
| **Pre-Execution Estimated Cost** | `\$0.0000126 USD` |

---

## 3. Response Telemetry

| Field | Returned Value |
| :--- | :--- |
| **HTTP Status Code** | `200 OK` |
| **OpenAny Request ID** | `0743400fadffb4e5fa37eacbe28eb0fa` |
| **Created Timestamp** | `1794379023` |
| **Model Executed** | `MiniMax-M2.5` |
| **Prompt Tokens** | `52` (cached: 14) |
| **Completion Tokens** | `8` |
| **Total Tokens** | `60` |
| **Assistant Content** | `"<think>The user says: \"Respond with one</think>\n\n"` |
| **Finish Reason** | `length` |
| **Internal OpenAny Cost Metric** | `21` |
| **AgentFlight Calculated Billed Cost**| `\$0.0000252 USD` |
| **Roundtrip Gateway Latency** | `1,767.89 ms` |
| **Flight Cassette Path** | `tests/cassettes/openany_live_attribution.flight.json` |
| **Cassette SHA-256 Head Hash** | `48c8c8a71ea94eae0029372af6bcd6f2b674780385ec19165b256384e5d50aab` |

---

## 4. Verification Checkpoint for OpenAny Backend Team

To complete Phase Two verification, Pistis / OpenAny Engineering can query their gateway ledger for:

```sql
SELECT
    request_id,
    partner_id,
    model,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    created_at
FROM gateway_requests
WHERE request_id = '0743400fadffb4e5fa37eacbe28eb0fa'
   OR (partner_id = 'agentflight' AND created_at >= '2026-11-11 06:36:00' AND created_at <= '2026-11-11 06:38:00');
```

Expected matching attributes:
- `request_id`: `0743400fadffb4e5fa37eacbe28eb0fa`
- `partner_id`: `agentflight`
- `model`: `MiniMax-M2.5`
- `total_tokens`: `60`
