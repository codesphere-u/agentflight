# Partnership Architecture & Commercial Discussion Memo: OpenAny & AgentFlight

**To:** Pistis (Founder, OpenAny / Alephant AI LLC)  
**From:** Akandwanaho Ivan Alvin (Founder, AgentFlight / Codesphere Innovations)  
**Date:** November 10, 2026  
**Subject:** Official AgentFlight + OpenAny Integration & Revenue-Sharing Partnership

---

## 1. Executive Summary

This document outlines the technical architecture, developer value proposition, and commercial partnership framework between **AgentFlight** and **OpenAny**.

AgentFlight has built a production-grade, first-class provider integration for OpenAny on branch `feat/openany-provider`, enabling developers to run OpenAny's 168+ models and 3,200+ external APIs with:
1. **Pre-Execution Cost Circuit Breaking**: Eliminating accidental token overruns before requests hit the network.
2. **Deterministic Cassette Replay**: Allowing developers to test agent workflows with $0.00 API spend and `<0.02ms` latency using recorded golden cassettes.
3. **Tool-Smell Linter Auditing**: Helping developers audit and optimize OpenAny remote MCP tools against 10 ergonomics rules (`TS001`–`TS010`).

---

## 2. Technical Implementation Highlights

- **Seamless Provider Discovery**: Registered as `openany` in AgentFlight's provider registry (`get_provider("openany")`).
- **Standardized Transport**: Direct integration with `https://api.openany.si/v1` and `https://mcp.openany.si/mcp` using standard library Python with zero mandatory third-party dependencies.
- **Partner Header Attribution**: Every request transmits:
  - `User-Agent: agentflight/1.1.0 (partner=openany; https://github.com/codesphere-u/agentflight)`
  - `X-Partner-Id: agentflight`
- **Secret Redaction**: Strict in-memory masking of API keys and bearer tokens across cassettes, logs, and traces.
- **CLI Suite**: Developer-first CLI commands: `agentflight openany models`, `agentflight openany chat`, `agentflight openany lint-tools`, `agentflight openany replay`.

---

## 3. Commercial & Revenue-Sharing Structure

In the proposed partnership, AgentFlight will direct enterprise and open-source agent developers to OpenAny for model routing and tool execution. In return, usage originating from the AgentFlight integration generates a commercial revenue share for Codesphere Innovations.

### Technical Attribution Mechanisms Implemented
- Configurable `OPENANY_PARTNER_ID="agentflight"`
- Outbound header `X-Partner-Id: agentflight`
- Traceable client identifier in `User-Agent`

---

## 4. Key Questions for Discussion with Pistis

To finalize our commercial agreement and optimize the developer experience, we have outlined the following technical and operational questions:

### A. Attribution & Tracking
1. Does OpenAny’s backend gateway (`AIephant-AI-Agent-Gateway`) currently ingest and record `X-Partner-Id` headers or partner query parameters on `/v1/chat/completions` and `/mcp` requests?
2. Is there a partner portal, dashboard, or reporting API where Codesphere Innovations can view aggregated volume, active developer accounts, and attributed revenue?
3. Can partner referral codes be linked during account onboarding (e.g. `openany.si/?ref=agentflight` or a CLI flag during `openany auth`)?

### B. Developer Credits & Onboarding
1. For developer trial credits: What is the preferred onboarding flow for new users coming through AgentFlight?
2. Once our team registers our development email, what is the fastest procedure for Pistis to provision the development test credits?

### C. Tool Catalog Ergonomics
1. In our live audit of OpenAny's remote MCP tools (`mcp.openany.si/mcp`), AgentFlight's linter identified high lexical similarity between adjacent tool operations (rule `TS008`) and missing property descriptions (rule `TS002`). Would OpenAny be interested in running AgentFlight's linter as a pre-commit or catalog validation check across their 3,200+ tools?

---

## 5. Recommended Joint Launch Roadmap

1. **Phase 1: Verification & Developer Credits**
   - Provide registered email to Pistis for development credits.
   - Run live smoke test with spending cap to verify live production billing reconciliation.
2. **Phase 2: Formalize Commercial Terms**
   - Align on revenue-share percentage (e.g. 10–20% of net usage generated through AgentFlight).
   - Agree on monthly or quarterly settlement rails (USDC / Stripe).
3. **Phase 3: Public Release & Co-Marketing**
   - Merge `feat/openany-provider` into `main`.
   - Publish joint blog post and social announcements on X (`@openanysi` & `@codesphere-u`).
   - Showcase AgentFlight on OpenAny's Ecosystem page and OpenAny on AgentFlight's official README.
