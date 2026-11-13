# OpenAny Remote MCP Ergonomics Audit Report

**Target Server:** `https://mcp.openany.si/mcp`  
**Protocol:** JSON-RPC 2.0 (`tools/list`)  
**Audit Engine:** AgentFlight Static Tool-Smell Linter (`agentflight.linter.ToolSmellLinter`)  
**Rules Evaluated:** TS001 – TS010 (Agent Tool Ergonomics Specification)  
**Audit Date:** November 11, 2026 (06:38:00 UTC)  
**Evaluator:** Akandwanaho Ivan Alvin (AgentFlight)  

---

## 1. Executive Summary

AgentFlight queried OpenAny's live remote MCP endpoint (`https://mcp.openany.si/mcp`) to evaluate the ergonomic readiness and token footprint of its published tools when ingested into production AI agent context windows.

| Metric | Measured Value | Benchmark Threshold |
| :--- | :--- | :--- |
| **Tools Audited** | **50** (primary catalog page) | — |
| **Agent Ergonomics Score** | **0 / 100** | &ge; 80 (Production Ready) |
| **Ergonomics Grade** | **F** | A / B |
| **Raw Tool Token Footprint** | **28,646 tokens / turn** | &le; 2,500 tokens / turn |
| **Total Ergonomic Findings** | **151** | 0 |
| **Errors** | **83** | 0 |
| **Warnings** | **68** | &le; 3 |

---

## 2. Rule Violations Breakdown

| Rule ID | Name | Severity | Count | Primary Impact on LLM Agents |
| :--- | :--- | :--- | :--- | :--- |
| **TS008** | Schema Validation / Untyped Properties | Error | **83** | Causes models to hallucinate argument types or send malformed JSON payloads. |
| **TS002** | Undocumented Properties | Warning | **22** | Model must infer property meaning from name alone; high ambiguity on cryptic parameters. |
| **TS007** | Missing `required` Array | Warning | **16** | Model cannot determine which fields are mandatory vs optional, causing redundant parameter queries. |
| **TS009** | Schema Redundancy / Empty Schema Wrappers | Warning | **16** | Wastes token budget on redundant nested structures without semantic value. |
| **TS004** | Excessive Property Name Length / Naming Smell | Warning | **10** | Distorts prompt token budget and confuses attention heads on long names. |
| **TS003** | Excessive Nesting Depth (&gt; 3 levels) | Warning | **4** | Deeply nested objects degrade function-calling accuracy in small and medium models. |

---

## 3. Real-World Findings Samples

### 3.1 TS008: Schema Error & Untyped Properties
```json
{
  "tool": "accurlex_post_law_search_deep_accurlex_law_search",
  "rule_id": "TS008",
  "severity": "error",
  "message": "Property 'query' schema lacks explicit primitive type or valid JSON schema structure."
}
```

### 3.2 TS007 & TS002: Missing Required Array and Missing Descriptions
```json
{
  "tool": "aihot_get_api_v1_agent_latest",
  "rule_id": "TS007",
  "severity": "warning",
  "message": "Tool defines 6 properties but omits the top-level 'required' array."
}
```

### 3.3 TS003: Excessive Nesting Depth
```json
{
  "tool": "accurlex_post_qa_deep_accurlex_legal_qa",
  "rule_id": "TS003",
  "severity": "warning",
  "message": "Tool inputSchema has nesting depth 4 (exceeds max recommended depth 3)."
}
```

---

## 4. Why This Validates the AgentFlight × OpenAny Partnership

This audit demonstrates the exact problem AgentFlight was designed to solve for OpenAny users:

1. **Breadth vs. Usability:** OpenAny provides access to 168+ models and 3,200+ external APIs. However, raw OpenAPI-to-MCP imports dump **28,646 tokens** into the prompt every single turn.
2. **Context Blowout:** In an agent loop with 10 turns, unoptimized schemas consume **286,460 tokens** in system prompts alone—costing developers dollars per interaction and pushing models toward context limits.
3. **The AgentFlight Solution:**
   - **`agentflight compile`** trims schemas by up to **78%**, stripping untyped metadata, pruning empty wrappers, and enforcing TS001-TS010 compliance.
   - **`TrajectoryCircuitBreaker`** halts runaway loops before unoptimized tools trigger token exhaustion.
   - **`FlightRecorder`** captures exact tool execution errors so developers can patch schemas deterministically.
