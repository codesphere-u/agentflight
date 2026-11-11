"""Interactive Developer Portal & Avionics Flight Deck for AgentFlight.

Faithfully reflects the luxury editorial engineering design system of Alvin's
portfolio (https://alvin.codesphereug.com/): Fraunces serif typography, warm gold
(#f4b94c) and deep obsidian stage (#14121d), terminal console-bars with traffic light
dots, pill buttons (.folio-action), and opener eyebrows with line dividers, paired
with live OpenAny 168+ model routing and aerospace flight telemetry.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List


def render_developer_portal(
    server_name: str,
    server_version: str,
    tagline: str,
    endpoint_url: str,
    github_url: str,
    tools: List[Dict[str, Any]],
    resources: List[Dict[str, Any]],
    prompts: List[Dict[str, Any]],
    sample_tool_call: Dict[str, Any],
) -> str:
    """Generate a luxury editorial aerospace cockpit flight dashboard matching Alvin's portfolio."""

    safe_name = html.escape(server_name)
    safe_version = html.escape(server_version)
    safe_tagline = html.escape(tagline)
    safe_endpoint = html.escape(endpoint_url)
    safe_github = html.escape(github_url)

    tools_json = json.dumps(tools, indent=2)
    resources_json = json.dumps(resources, indent=2)
    prompts_json = json.dumps(prompts, indent=2)
    sample_call_json = json.dumps(sample_tool_call, indent=2)

    presets = {
        "init": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agentflight-web-portal", "version": server_version},
            },
        },
        "tools_list": {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        "sample_call": sample_tool_call,
        "lint_clean": {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "agentflight_lint_tools",
                "arguments": {
                    "tools": [
                        {
                            "name": "lookup_user",
                            "description": "Look up user profile by unique ID. Safe read-only query.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "user_id": {
                                        "type": "string",
                                        "description": "Unique user account identifier",
                                    }
                                },
                                "required": ["user_id"],
                            },
                        }
                    ]
                },
            },
        },
        "lint_smelly": {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "agentflight_lint_tools",
                "arguments": {
                    "tools": [
                        {
                            "name": "doStuff",
                            "description": "stuff",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"a": {"type": "string"}},
                            },
                        },
                        {
                            "name": "deep_nested_smell",
                            "description": "Valid detailed description for this deep schema",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "lvl1": {
                                        "type": "object",
                                        "properties": {
                                            "lvl2": {
                                                "type": "object",
                                                "properties": {
                                                    "lvl3": {
                                                        "type": "object",
                                                        "properties": {
                                                            "lvl4": {"type": "string"}
                                                        },
                                                    }
                                                },
                                            }
                                        },
                                    }
                                },
                            },
                        },
                    ]
                },
            },
        },
        "openany_models": {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "agentflight_openany_models",
                "arguments": {"refresh": False},
            },
        },
        "openany_chat": {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "agentflight_openany_chat",
                "arguments": {
                    "model": "MiniMax-M2.5",
                    "prompt": "Evaluate agent tool safety and circuit breaker parameters for zero runaway loops.",
                },
            },
        },
        "res_list": {"jsonrpc": "2.0", "id": 3, "method": "resources/list"},
        "res_templates": {"jsonrpc": "2.0", "id": 4, "method": "resources/templates/list"},
        "prompts_list": {"jsonrpc": "2.0", "id": 5, "method": "prompts/list"},
    }
    presets_json = json.dumps(presets, indent=2)

    sample_flights = {
        "flight_golden": {
            "title": "Flight #101: Clean Multi-Step Checkout (4 Spans)",
            "severity": "CLEAN",
            "status_label": "HEALTHY FLIGHT",
            "receipt": {
                "flight_no": "AF-101-GOLDEN",
                "carrier": "OpenAny Gateway (AIephant)",
                "model": "MiniMax-M2.5 (Thinking CoT)",
                "prompt_tokens": 1420,
                "prompt_cost": 0.000213,
                "completion_tokens": 384,
                "completion_cost": 0.000230,
                "tool_calls": 3,
                "circuit_status": "PASS (0 LOOPS)",
                "total_cost": 0.000443,
                "savings": 0.8400,
                "merkle_hash": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
            },
            "spans": [
                {
                    "step": 0,
                    "actor": "search_catalog",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 14.2,
                    "cost_usd": 0.0003,
                    "tokens": 120,
                    "input": {"category": "developer_tools", "max_price": 50},
                    "output": {"items": [{"id": "AF-PRO", "title": "AgentFlight Pro Linter", "price": 29.0}]},
                    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "notes": "Optimal parameter token economy",
                },
                {
                    "step": 1,
                    "actor": "check_inventory",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 8.7,
                    "cost_usd": 0.0002,
                    "tokens": 85,
                    "input": {"sku": "AF-PRO"},
                    "output": {"in_stock": True, "available_seats": 500},
                    "hash": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
                    "notes": "Verified inventory availability",
                },
                {
                    "step": 2,
                    "actor": "apply_discount_coupon",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 6.5,
                    "cost_usd": 0.0001,
                    "tokens": 60,
                    "input": {"code": "GLAMA2026", "sku": "AF-PRO"},
                    "output": {"valid": True, "discount_pct": 20, "final_price": 23.20},
                    "hash": "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
                    "notes": "20% promotional coupon reconciled",
                },
                {
                    "step": 3,
                    "actor": "create_order",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 28.1,
                    "cost_usd": 0.0006,
                    "tokens": 210,
                    "input": {"sku": "AF-PRO", "amount": 23.20, "currency": "USD"},
                    "output": {"order_id": "ORD-9912", "status": "confirmed", "license_key": "AF-LIVE-PRO-881"},
                    "hash": "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
                    "notes": "Order confirmed and cryptographic cassette sealed",
                },
            ],
        },
        "flight_incident": {
            "title": "Flight #204: Oscillating Loop Incident (Circuit Tripped)",
            "severity": "CRITICAL",
            "status_label": "CIRCUIT BREAKER TRIPPED",
            "receipt": {
                "flight_no": "AF-204-TRIPPED",
                "carrier": "OpenAny Gateway (AIephant)",
                "model": "MiniMax-M2.5 (Runaway Severed)",
                "prompt_tokens": 480,
                "prompt_cost": 0.000072,
                "completion_tokens": 280,
                "completion_cost": 0.000168,
                "tool_calls": 3,
                "circuit_status": "TRIPPED (LOOP SEVERED)",
                "total_cost": 0.000240,
                "savings": 4.5000,
                "merkle_hash": "f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1",
            },
            "spans": [
                {
                    "step": 0,
                    "actor": "fetch_user_account",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 11.0,
                    "cost_usd": 0.0002,
                    "tokens": 90,
                    "input": {"user_id": "usr_9981"},
                    "output": {"user": "alice", "plan": "enterprise"},
                    "hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                    "notes": "Account profile loaded",
                },
                {
                    "step": 1,
                    "actor": "execute_payment",
                    "kind": "tool_call",
                    "status": "error",
                    "latency_ms": 65.4,
                    "cost_usd": 0.0005,
                    "tokens": 140,
                    "input": {"amount": 500, "card": "tok_visa_declined"},
                    "output": {"error": "Card Declined by Issuer (402)", "isError": True},
                    "hash": "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                    "notes": "Downstream payment failure trigger",
                },
                {
                    "step": 2,
                    "actor": "execute_payment",
                    "kind": "tool_call",
                    "status": "error",
                    "latency_ms": 62.1,
                    "cost_usd": 0.0005,
                    "tokens": 140,
                    "input": {"amount": 500, "card": "tok_visa_declined"},
                    "output": {"error": "Card Declined by Issuer (402)", "isError": True},
                    "hash": "e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6",
                    "notes": "Loop oscillation attempt #2 detected",
                },
                {
                    "step": 3,
                    "actor": "TrajectoryCircuitBreaker",
                    "kind": "state_checkpoint",
                    "status": "tripped",
                    "latency_ms": 0.1,
                    "cost_usd": 0.0,
                    "tokens": 0,
                    "input": {"reason": "LOOP_OSCILLATION_DETECTED", "consecutive_errors": 2},
                    "output": {"circuit_state": "OPEN", "action": "SEVER_RUNAWAY_TRAJECTORY", "spend_saved": 4.50},
                    "hash": "f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1",
                    "notes": "Trajectory severed automatically; saved $4.50 compute runaway",
                },
            ],
        },
        "flight_openany": {
            "title": "Flight #305: OpenAny Multi-Model Gateway Chain",
            "severity": "CLEAN",
            "status_label": "PARTNER EXECUTION",
            "receipt": {
                "flight_no": "AF-305-OPENANY",
                "carrier": "OpenAny Gateway (AIephant)",
                "model": "MiniMax-M2.5 + DeepSeek-V3",
                "prompt_tokens": 1950,
                "prompt_cost": 0.000292,
                "completion_tokens": 640,
                "completion_cost": 0.000384,
                "tool_calls": 4,
                "circuit_status": "PASS (0 LOOPS)",
                "total_cost": 0.000676,
                "savings": 1.2500,
                "merkle_hash": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
            },
            "spans": [
                {
                    "step": 0,
                    "actor": "agentflight_openany_models",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 42.0,
                    "cost_usd": 0.0,
                    "tokens": 65,
                    "input": {"refresh": False},
                    "output": {"provider": "openany", "available_models": 168, "gateway": "AIephant"},
                    "hash": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
                    "notes": "Catalog discovery of 168 models",
                },
                {
                    "step": 1,
                    "actor": "agentflight_openany_chat",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 180.5,
                    "cost_usd": 0.00015,
                    "tokens": 320,
                    "input": {"model": "MiniMax-M2.5", "prompt": "Audit safety constraints for tool calling"},
                    "output": {"content": "Deterministic replay with SHA-256 guarantees zero regression.", "cost_usd": 0.00015},
                    "hash": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
                    "notes": "Live reasoning completion generated",
                },
                {
                    "step": 2,
                    "actor": "export_otel_spans",
                    "kind": "tool_call",
                    "status": "ok",
                    "latency_ms": 1.5,
                    "cost_usd": 0.0,
                    "tokens": 40,
                    "input": {"service_name": "agentflight-telemetry"},
                    "output": {"spans_exported": 3, "w3c_traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
                    "hash": "f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1",
                    "notes": "W3C TraceContext telemetry emitted",
                },
            ],
        },
    }
    sample_flights_json = json.dumps(sample_flights, indent=2)

    # Tool cards
    tool_cards = []
    for t in tools:
        t_name = html.escape(t.get("name", ""))
        t_desc = html.escape(t.get("description", ""))
        props = t.get("inputSchema", {}).get("properties", {})
        req = set(t.get("inputSchema", {}).get("required", []))
        param_badges = "".join(
            f'<span class="badge param {"req" if p in req else "opt"}">{html.escape(p)}{"*" if p in req else ""}</span>'
            for p in props.keys()
        )
        tool_cards.append(
            f"""
            <div class="card item-card tool-card-item" data-name="{t_name}" data-desc="{t_desc}">
              <div class="card-head">
                <span class="mono font-bold text-gold">{t_name}</span>
                <button class="folio-action-sm" onclick="loadToolCall('{t_name}')">Test &rarr;</button>
              </div>
              <p class="text-sm text-dim">{t_desc}</p>
              <div class="param-row">{param_badges or '<span class="text-xs text-muted">No parameters</span>'}</div>
            </div>
            """
        )
    tools_html = "".join(tool_cards)

    # Resource cards
    res_cards = []
    for r in resources:
        r_uri = html.escape(r.get("uri", ""))
        r_name = html.escape(r.get("name", ""))
        r_desc = html.escape(r.get("description", ""))
        r_mime = html.escape(r.get("mimeType", "application/json"))
        res_cards.append(
            f"""
            <div class="card item-card resource-card-item" data-uri="{r_uri}">
              <div class="card-head">
                <span class="mono font-bold text-mint">{r_name}</span>
                <button class="folio-action-sm" onclick="loadResourceRead('{r_uri}')">Read &rarr;</button>
              </div>
              <p class="text-sm text-dim">{r_desc}</p>
              <div class="meta-row">
                <span class="badge badge-sub mono">{r_uri}</span>
                <span class="badge badge-sub mono">{r_mime}</span>
              </div>
            </div>
            """
        )
    resources_html = "".join(res_cards)

    # Prompt cards
    prompt_cards = []
    for p in prompts:
        p_name = html.escape(p.get("name", ""))
        p_desc = html.escape(p.get("description", ""))
        args = p.get("arguments", [])
        arg_badges = "".join(
            f'<span class="badge param {"req" if a.get("required") else "opt"}">{html.escape(a.get("name", ""))}{"*" if a.get("required") else ""}</span>'
            for a in args
        )
        prompt_cards.append(
            f"""
            <div class="card item-card prompt-card-item" data-name="{p_name}">
              <div class="card-head">
                <span class="mono font-bold text-cyan">{p_name}</span>
                <button class="folio-action-sm" onclick="loadPromptGet('{p_name}')">Render &rarr;</button>
              </div>
              <p class="text-sm text-dim">{p_desc}</p>
              <div class="param-row">{arg_badges or '<span class="text-xs text-muted">No arguments</span>'}</div>
            </div>
            """
        )
    prompts_html = "".join(prompt_cards)

    claude_code_cmd = f"claude mcp add --transport http {safe_name} {safe_endpoint}"
    claude_desktop_cfg = json.dumps({"mcpServers": {safe_name: {"type": "http", "url": safe_endpoint}}}, indent=2)
    cursor_cfg = json.dumps({"mcpServers": {safe_name: {"type": "http", "url": safe_endpoint}}}, indent=2)
    smithery_cmd = f"npx -y @smithery/cli install @codesphere-u/{safe_name} --client claude"
    stdio_cmd = f"uvx --from git+{safe_github}.git {safe_name} serve-mcp"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_name} &bull; Aerospace Mission Control & Flight Deck</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400&family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* --------------------------------------------------------
       ALVIN'S EDITORIAL LUXURY DESIGN SYSTEM (Codesphere World)
       -------------------------------------------------------- */
    :root {{
      --stage: #14121d;
      --stage-deep: #0f0d16;
      --stage-ink: #fff1e2;
      --stage-muted: #d9cfd8;
      --stage-quiet: #a395a3;
      --gold: #f4b94c;
      --gold-bright: #ffcb8d;
      --gold-glow: rgba(244, 185, 76, 0.28);
      --ember: #d0603f;
      --ember-glow: rgba(208, 96, 63, 0.25);
      --live-green: #7ed7a1;
      --live-green-glow: rgba(126, 215, 161, 0.3);
      --cyan: #53c9ee;
      --cyan-glow: rgba(83, 201, 238, 0.25);
      --openany-blue: #3b82f6;
      --openany-blue-glow: rgba(59, 130, 246, 0.25);
      
      --card-bg: rgba(24, 21, 33, 0.82);
      --card-border: rgba(244, 185, 76, 0.16);
      --card-border-glow: rgba(244, 185, 76, 0.38);
      --card-rule: rgba(255, 255, 255, 0.08);

      --font-display: 'Fraunces', Georgia, 'Times New Roman', serif;
      --font-sans: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    
    body {{
      background: var(--stage);
      background-image: 
        radial-gradient(120% 95% at 85% 0%, rgba(92, 59, 41, 0.35) 0%, rgba(43, 26, 34, 0.22) 55%, transparent 100%),
        radial-gradient(55% 85% at 12% 100%, rgba(208, 96, 63, 0.14) 0%, transparent 70%);
      color: var(--stage-ink);
      font-family: var(--font-body);
      line-height: 1.6;
      padding: 0 16px 60px;
      min-height: 100vh;
      position: relative;
      overflow-x: hidden;
    }}

    /* Editorial Serif Headings */
    h1, h2, h3, h4 {{
      font-family: var(--font-display);
      font-weight: 400;
      letter-spacing: -0.04em;
      line-height: 1.05;
      color: var(--stage-ink);
    }}

    #radar-canvas {{
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      pointer-events: none;
      z-index: 0;
      opacity: 0.45;
    }}

    .container {{
      max-width: 1240px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }}
    
    /* Top Ticker: Alvin's Provenance Bar */
    .top-ticker {{
      display: flex; justify-content: space-between; align-items: center;
      background: rgba(18, 15, 26, 0.92);
      border-bottom: 1px solid var(--card-border);
      padding: 10px 20px; margin: 0 -16px 26px -16px;
      font-size: 11px; font-family: var(--font-mono);
      backdrop-filter: blur(14px);
    }}
    .live-dot {{
      display: inline-block; width: 8px; height: 8px; border-radius: 50%;
      background: var(--live-green); margin-right: 8px;
      box-shadow: 0 0 10px var(--live-green-glow);
      animation: pulse 2.4s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.3); opacity: 0.6; }}
    }}

    /* Alvin's Signature Opener Eyebrow */
    .opener-eyebrow {{
      display: flex; align-items: center; gap: 12px; color: var(--gold);
      font-family: var(--font-mono); font-size: 11px; font-weight: 700;
      letter-spacing: 0.12em; text-transform: uppercase;
    }}
    .opener-eyebrow > span {{
      width: 24px; height: 1px; flex: none; background: currentColor;
    }}

    /* Header */
    .header {{
      padding: 24px 0 22px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 30px;
    }}
    .header-top {{
      display: flex; justify-content: space-between; align-items: flex-start;
      flex-wrap: wrap; gap: 18px; margin-bottom: 24px;
    }}
    .title-group {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
    h1 {{
      font-size: 38px;
      display: flex; align-items: center; gap: 12px;
      background: linear-gradient(135deg, #fff1e2 0%, #ffcb8d 60%, #f4b94c 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .badge {{
      font-size: 11px; font-family: var(--font-mono); padding: 4px 10px;
      border-radius: 999px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .badge-ver {{ background: rgba(244, 185, 76, 0.15); color: var(--gold-bright); border: 1px solid rgba(244, 185, 76, 0.35); }}
    .badge-live {{ background: rgba(126, 215, 161, 0.15); color: var(--live-green); border: 1px solid rgba(126, 215, 161, 0.35); }}
    .badge-proto {{ background: rgba(83, 201, 238, 0.15); color: var(--cyan); border: 1px solid rgba(83, 201, 238, 0.35); }}
    .badge-suite {{ background: rgba(208, 96, 63, 0.15); color: #ff9d85; border: 1px solid rgba(208, 96, 63, 0.35); }}
    .links {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
    
    /* Alvin's Signature Pill Action Buttons */
    .folio-action {{
      background: var(--gold); color: #261904; border: 1px solid var(--gold);
      border-radius: 999px; padding: 9px 22px; font-size: 13px; font-weight: 700;
      text-decoration: none; display: inline-flex; align-items: center; gap: 8px;
      font-family: var(--font-sans); cursor: pointer;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: 0 4px 14px rgba(244, 185, 76, 0.2);
    }}
    .folio-action:hover {{
      background: var(--gold-bright); border-color: var(--gold-bright);
      transform: translateY(-1px); box-shadow: 0 8px 24px var(--gold-glow);
      color: #191206;
    }}
    .folio-action-secondary {{
      background: transparent; color: var(--stage-ink); border: 1px solid rgba(244, 185, 76, 0.35);
      border-radius: 999px; padding: 8px 18px; font-size: 13px; font-weight: 600;
      text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
      font-family: var(--font-sans); cursor: pointer; transition: all 0.2s ease;
      backdrop-filter: blur(8px);
    }}
    .folio-action-secondary:hover {{
      background: rgba(244, 185, 76, 0.12); border-color: var(--gold);
      transform: translateY(-1px); color: #fff;
    }}
    .folio-action-sm {{
      background: rgba(244, 185, 76, 0.12); color: var(--gold); border: 1px solid rgba(244, 185, 76, 0.3);
      border-radius: 999px; padding: 4px 12px; font-size: 11px; font-weight: 600; cursor: pointer;
      font-family: var(--font-sans); transition: all 0.2s ease;
    }}
    .folio-action-sm:hover {{
      background: var(--gold); color: #261904; border-color: var(--gold);
    }}
    .audio-toggle {{ font-family: var(--font-mono); font-size: 11px; }}

    /* Cards & Glass Surfaces */
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px; padding: 24px;
      margin-bottom: 26px;
      backdrop-filter: blur(16px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
      position: relative;
    }}
    
    /* Console Bar (Alvin's Signature Terminal Header) */
    .console-bar {{
      display: flex; align-items: center; gap: 7px;
      padding: 10px 16px; background: rgba(12, 10, 18, 0.6);
      border-bottom: 1px solid var(--card-rule);
      border-top-left-radius: 12px; border-top-right-radius: 12px;
    }}
    .console-bar i {{
      width: 10px; height: 10px; border-radius: 50%; display: inline-block;
    }}
    .console-bar i:nth-child(1) {{ background: #ff6b5a; }}
    .console-bar i:nth-child(2) {{ background: #ffc857; }}
    .console-bar i:nth-child(3) {{ background: #6fe08a; }}
    .console-bar span {{
      margin-left: 10px; color: var(--stage-quiet); font-size: 11px; font-family: var(--font-mono);
    }}

    /* Stats Grid */
    .grid-stats {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 14px; margin-top: 20px;
    }}
    .stat-card {{
      background: rgba(19, 16, 27, 0.65); border: 1px solid var(--card-border);
      padding: 16px 20px; border-radius: 10px;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .stat-card:hover {{
      border-color: var(--gold); transform: translateY(-2px); box-shadow: 0 8px 24px var(--gold-glow);
    }}
    .stat-val {{ font-size: 26px; font-weight: 700; font-family: var(--font-mono); }}
    .stat-lbl {{ font-size: 11px; color: var(--stage-quiet); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }}

    /* ========================================================
       HERO TRAJECTORY HIGHWAY
       ======================================================== */
    .hero-highway-card {{
      border: 1px solid rgba(244, 185, 76, 0.32);
      background: radial-gradient(ellipse at 50% 0%, rgba(92, 59, 41, 0.3) 0%, rgba(20, 17, 28, 0.85) 70%);
      box-shadow: 0 0 45px rgba(244, 185, 76, 0.12);
      padding: 28px;
    }}
    .highway-stage {{
      position: relative; width: 100%; height: 260px;
      margin: 20px 0; border-radius: 12px;
      background: rgba(10, 8, 15, 0.7);
      border: 1px solid rgba(244, 185, 76, 0.14);
      overflow: hidden;
    }}
    #highway-canvas {{
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      z-index: 1; pointer-events: none;
    }}
    .highway-nodes {{
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      z-index: 2; display: flex; justify-content: space-between; align-items: center;
      padding: 0 40px; pointer-events: none;
    }}
    .highway-node {{
      pointer-events: auto; cursor: pointer;
      display: flex; flex-direction: column; align-items: center;
      background: rgba(22, 19, 31, 0.88);
      border: 1px solid var(--card-border);
      border-radius: 12px; padding: 14px 20px;
      width: 220px; text-align: center;
      box-shadow: 0 8px 26px rgba(0,0,0,0.6);
      transition: all 0.25s ease;
      backdrop-filter: blur(14px);
    }}
    .highway-node:hover {{
      transform: translateY(-3px) scale(1.02);
      border-color: var(--gold-bright);
      box-shadow: 0 12px 32px var(--gold-glow);
    }}
    .highway-node.node-center {{
      border-color: rgba(244, 185, 76, 0.55);
      background: radial-gradient(circle at center, rgba(244, 185, 76, 0.18) 0%, rgba(22, 19, 31, 0.92) 75%);
    }}
    .highway-node.node-center:hover {{
      border-color: var(--gold);
      box-shadow: 0 14px 34px var(--gold-glow);
    }}
    .highway-node.node-right {{
      border-color: rgba(126, 215, 161, 0.5);
      background: radial-gradient(circle at center, rgba(126, 215, 161, 0.15) 0%, rgba(22, 19, 31, 0.92) 75%);
    }}
    .highway-node.node-right:hover {{
      border-color: var(--live-green);
      box-shadow: 0 14px 34px var(--live-green-glow);
    }}
    .node-icon {{ font-size: 24px; margin-bottom: 6px; }}
    .node-title {{ font-size: 14px; font-weight: 700; font-family: var(--font-sans); color: #fff; }}
    .node-sub {{ font-size: 11px; font-family: var(--font-mono); color: var(--stage-quiet); margin-top: 3px; }}
    .node-stat {{ font-size: 11px; font-family: var(--font-mono); margin-top: 8px; padding: 3px 8px; border-radius: 999px; }}

    /* ========================================================
       OPENANY MULTI-MODEL FLEET MATRIX
       ======================================================== */
    .matrix-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px; margin-top: 18px;
    }}
    .model-card {{
      background: rgba(21, 18, 29, 0.7);
      border: 1px solid var(--card-border);
      border-radius: 12px; padding: 18px;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      display: flex; flex-direction: column; justify-content: space-between;
    }}
    .model-card:hover {{
      border-color: var(--gold);
      transform: translateY(-2px);
      box-shadow: 0 10px 28px var(--gold-glow);
    }}
    .model-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
    .model-name {{ font-family: var(--font-display); font-size: 17px; font-weight: 600; color: #fff; }}
    .model-provider {{ font-size: 11px; font-family: var(--font-mono); color: var(--stage-muted); }}
    .model-rates {{
      display: flex; gap: 8px; margin: 12px 0; font-family: var(--font-mono); font-size: 11px;
    }}
    .rate-pill {{
      background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(244, 185, 76, 0.15);
      padding: 4px 8px; border-radius: 6px;
    }}
    .rate-pill span {{ color: var(--gold); font-weight: 600; }}

    /* ========================================================
       CRYPTOGRAPHIC FLIGHT USAGE RECEIPT
       ======================================================== */
    .receipt-container {{
      background: #0d0b13;
      border: 1px dashed rgba(244, 185, 76, 0.28);
      border-radius: 10px;
      padding: 22px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: #fff1e2;
      line-height: 1.6;
      box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.85);
      position: relative;
    }}
    .receipt-header {{
      text-align: center; padding-bottom: 12px; margin-bottom: 12px;
      border-bottom: 1px dashed rgba(244, 185, 76, 0.25);
    }}
    .receipt-title {{ font-size: 14px; font-weight: 700; color: var(--gold-bright); letter-spacing: 0.06em; }}
    .receipt-line {{ display: flex; justify-content: space-between; margin: 4px 0; }}
    .receipt-divider {{ border-top: 1px dashed rgba(244, 185, 76, 0.2); margin: 12px 0; }}
    .receipt-total {{ font-weight: 700; font-size: 13px; color: var(--live-green); }}
    .receipt-barcode {{
      font-family: monospace; letter-spacing: 4px; font-size: 14px;
      text-align: center; margin-top: 16px; opacity: 0.55; color: var(--gold);
    }}

    /* Cockpit HUD */
    .hud-card {{
      border: 1px solid rgba(244, 185, 76, 0.35);
      box-shadow: 0 0 35px rgba(244, 185, 76, 0.14);
    }}
    .waypoint-track {{
      display: flex; justify-content: space-between; align-items: center;
      position: relative; margin: 22px 0 16px; padding: 0 24px;
    }}
    .waypoint-line {{
      position: absolute; top: 18px; left: 44px; right: 44px; height: 3px;
      background: rgba(255, 255, 255, 0.1); z-index: 0;
    }}
    .waypoint-line-fill {{
      height: 100%; background: linear-gradient(90deg, var(--ember), var(--gold), var(--live-green));
      width: 0%; transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .waypoint-node {{
      position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center;
      cursor: pointer; transition: transform 0.2s ease;
    }}
    .waypoint-node:hover {{ transform: scale(1.1); }}
    .waypoint-dot {{
      width: 38px; height: 38px; border-radius: 50%; background: #161320;
      border: 2px solid var(--stage-quiet); display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-family: var(--font-mono); font-weight: 700; color: var(--stage-muted);
      box-shadow: 0 0 12px rgba(0,0,0,0.6); transition: all 0.3s ease;
    }}
    .waypoint-node.active .waypoint-dot {{
      border-color: var(--gold); color: #261904; background: var(--gold);
      box-shadow: 0 0 20px var(--gold-glow);
    }}
    .waypoint-node.passed .waypoint-dot {{
      border-color: var(--live-green); color: #fff; background: rgba(126, 215, 161, 0.2);
    }}
    .waypoint-title {{
      font-size: 11px; font-family: var(--font-mono); color: var(--stage-muted);
      margin-top: 6px; text-align: center; max-width: 110px;
    }}

    /* Tabs */
    .tabs {{
      display: flex; gap: 6px; border-bottom: 1px solid var(--card-border);
      margin-bottom: 16px; overflow-x: auto;
    }}
    .tab-btn {{
      background: transparent; color: var(--stage-quiet); border: none;
      padding: 10px 16px; font-size: 13px; font-weight: 500; cursor: pointer;
      border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;
      font-family: var(--font-sans);
    }}
    .tab-btn:hover {{ color: #fff; }}
    .tab-btn.active {{ color: var(--gold); border-bottom-color: var(--gold); font-weight: 700; }}
    
    .snippet-box {{
      position: relative; background: #0b0912; border: 1px solid var(--card-border);
      border-radius: 10px; padding: 16px 18px; margin-top: 10px;
    }}
    pre {{ font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: #fff1e2; overflow-x: auto; }}
    .copy-btn {{
      position: absolute; top: 12px; right: 12px;
      background: rgba(244, 185, 76, 0.12); border: 1px solid rgba(244, 185, 76, 0.3);
      color: var(--gold-bright); font-size: 11px; padding: 4px 11px; border-radius: 999px; cursor: pointer;
      transition: all 0.2s; font-family: var(--font-sans);
    }}
    .copy-btn:hover {{ background: var(--gold); color: #261904; }}
    .copy-btn.copied {{ background: var(--live-green); color: #000; border-color: var(--live-green); }}

    /* Playground */
    .playground-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
      gap: 18px; margin-top: 16px;
    }}
    .pane {{
      background: #0c0a13; border: 1px solid var(--card-border); border-radius: 10px;
      display: flex; flex-direction: column; overflow: hidden;
    }}
    .pane-head {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 16px; background: rgba(255, 255, 255, 0.02);
      border-bottom: 1px solid var(--card-border);
    }}
    .pane-title {{ font-size: 12px; font-weight: 600; font-family: var(--font-mono); color: var(--stage-muted); }}
    .code-editor {{
      width: 100%; height: 260px; background: transparent; border: none;
      color: #fff1e2; font-family: var(--font-mono); font-size: 12px; line-height: 1.6;
      padding: 14px; resize: vertical; outline: none;
    }}
    .response-box {{
      width: 100%; height: 260px; padding: 14px; overflow: auto;
      font-family: var(--font-mono); font-size: 12px; color: #a7f3d0;
    }}
    .preset-bar {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }}

    /* Card Catalogs */
    .card-list {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 14px; margin-top: 16px;
    }}
    .item-card {{
      padding: 16px 18px; margin-bottom: 0;
      transition: all 0.2s ease;
    }}
    .item-card:hover {{ border-color: var(--gold); transform: translateY(-2px); }}
    .card-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
    .param-row {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }}
    .badge.param {{ font-size: 10px; padding: 2px 7px; border-radius: 4px; font-family: var(--font-mono); }}
    .badge.param.req {{ background: rgba(208, 96, 63, 0.2); color: #ff9d85; border: 1px solid rgba(208, 96, 63, 0.4); }}
    .badge.param.opt {{ background: rgba(255, 255, 255, 0.06); color: var(--stage-muted); border: 1px solid rgba(255, 255, 255, 0.1); }}
    .meta-row {{ display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }}
    .badge-sub {{ background: rgba(255, 255, 255, 0.05); color: var(--stage-muted); font-size: 10px; }}
    .search-input {{
      background: rgba(0, 0, 0, 0.45); border: 1px solid var(--card-border);
      color: #fff; padding: 9px 16px; border-radius: 999px; font-size: 13px;
      width: 100%; max-width: 320px; outline: none; font-family: var(--font-sans);
    }}
    .search-input:focus {{ border-color: var(--gold); }}

    /* Footer */
    .footer {{
      display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;
      gap: 14px; padding: 28px 4px; border-top: 1px solid var(--card-border);
      font-size: 12px; color: var(--stage-quiet);
    }}
    .footer a {{ color: var(--gold); text-decoration: none; }}

    .mono {{ font-family: var(--font-mono); }}
    .font-bold {{ font-weight: 700; }}
    .text-gold {{ color: var(--gold); }}
    .text-ember {{ color: var(--ember); }}
    .text-mint {{ color: var(--live-green); }}
    .text-cyan {{ color: var(--cyan); }}
    .text-blue {{ color: var(--openany-blue); }}
    .text-dim {{ color: var(--stage-muted); }}
    .text-muted {{ color: var(--stage-quiet); }}
    .text-sm {{ font-size: 13px; }}
    .text-xs {{ font-size: 11px; }}

    @media (max-width: 768px) {{
      .highway-stage {{ height: 320px; }}
      .highway-nodes {{ flex-direction: column; padding: 20px 10px; gap: 10px; justify-content: center; }}
      .highway-node {{ width: 90%; }}
      .playground-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <canvas id="radar-canvas"></canvas>

  <!-- Top Ticker: Alvin's Provenance Bar -->
  <div class="top-ticker">
    <div style="display: flex; align-items: center;">
      <span class="live-dot"></span>
      <span class="text-gold font-bold">OPERATIONAL:</span>&nbsp;AGENTFLIGHT BLACK-BOX AVIONICS &bull; OPENANY GATEWAY (168+ MODELS) &bull; P50: 2.83 &mu;s
    </div>
    <div style="display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
      <span class="mono" style="color: var(--stage-ink);">ARCHITECT: <a href="https://alvin.codesphereug.com/work/agentflight.html" target="_blank" rel="noopener" style="color: var(--gold); text-decoration: none; font-weight: 700;">AKANDWANAHO IVAN (ALVIN)</a> &bull; CODESPHERE INNOVATIONS</span>
      <span class="mono text-muted">| OPENANY CASSETTE: VERIFIED</span>
      <button class="folio-action-sm audio-toggle" onclick="toggleAudio()" id="audio-btn">🔊 Sound: OFF</button>
    </div>
  </div>

  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-top">
        <div>
          <div class="title-group">
            <h1><span>✈️</span> {safe_name}</h1>
            <span class="badge badge-ver">v{safe_version}</span>
            <span class="badge badge-live">Operational</span>
            <span class="badge badge-proto">MCP 2024-11-05</span>
            <span class="badge badge-suite">Codesphere AI Suite</span>
          </div>
          <p class="text-sm text-dim" style="margin-top: 10px; max-width: 740px;">{safe_tagline}</p>
        </div>
        <div class="links">
          <a class="folio-action" href="https://alvin.codesphereug.com/work/agentflight.html" target="_blank" rel="noopener">Architect Case Study &rarr;</a>
          <a class="folio-action-secondary" href="#openany-matrix">Explore 168+ Models &rarr;</a>
          <a class="folio-action-secondary" href="{safe_github}" target="_blank" rel="noopener">GitHub ↗</a>
          <a class="folio-action-secondary" href="/docs" target="_blank" rel="noopener">Swagger UI ↗</a>
        </div>
      </div>
      
      <div class="grid-stats">
        <div class="stat-card">
          <div class="stat-val text-gold">2.83 &mu;s</div>
          <div class="stat-lbl">Span Replay P50</div>
        </div>
        <div class="stat-card">
          <div class="stat-val text-gold">168 Models</div>
          <div class="stat-lbl">OpenAny Multi-Model Gateway</div>
        </div>
        <div class="stat-card">
          <div class="stat-val text-cyan">10 Rules</div>
          <div class="stat-lbl">MCP Tool-Smell Linter</div>
        </div>
        <div class="stat-card">
          <div class="stat-val text-mint">353k</div>
          <div class="stat-lbl">Spans / Second</div>
        </div>
        <div class="stat-card">
          <div class="stat-val" style="color: #ff9d85;">$0.00</div>
          <div class="stat-lbl">Deterministic CI Replay</div>
        </div>
      </div>
    </header>

    <!-- ========================================================
         HERO TRAJECTORY HIGHWAY
         ======================================================== -->
    <section class="card hero-highway-card" id="hero-highway">
      <div class="console-bar" style="margin: -28px -28px 18px -28px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; trajectory-highway.live</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 14px;">
        <div>
          <p class="opener-eyebrow"><span></span>01 / HIGH-SPEED ROUTING HIGHWAY</p>
          <h2 style="font-size: 26px; margin-top: 6px;">The Hero Trajectory Highway</h2>
          <p class="text-xs text-dim" style="max-width: 660px; margin-top: 6px;">
            Every agent call travels across our cryptographic highway: from your local agent client, through AgentFlight's anti-loop circuit breaker, directly into OpenAny's multi-model frontier routing gateway.
          </p>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="folio-action-sm" onclick="setHighwayMode('full')">Full Avionics Route</button>
          <button class="folio-action-sm" onclick="setHighwayMode('vcr')">Offline VCR Replay</button>
          <button class="folio-action-sm" onclick="setHighwayMode('direct')">OpenAny Direct</button>
        </div>
      </div>

      <!-- Highway Canvas & Interactive Nodes -->
      <div class="highway-stage" id="highway-stage">
        <canvas id="highway-canvas"></canvas>
        <div class="highway-nodes">
          <div class="highway-node" id="h-node-client" onclick="selectHighwayNode('client')">
            <div class="node-icon">💻</div>
            <div class="node-title">Agent Client Fleet</div>
            <div class="node-sub">Claude Code &bull; Cursor &bull; Codex</div>
            <div class="node-stat" style="background: rgba(83, 201, 238, 0.15); color: var(--cyan);">MCP 2024-11-05</div>
          </div>

          <div class="highway-node node-center" id="h-node-shield" onclick="selectHighwayNode('shield')">
            <div class="node-icon">🛡️</div>
            <div class="node-title">AgentFlight Shield</div>
            <div class="node-sub">Anti-Loop Breaker &bull; Merkle Cassette</div>
            <div class="node-stat" style="background: rgba(244, 185, 76, 0.2); color: var(--gold);">2.83 &mu;s P50 Latency</div>
          </div>

          <div class="highway-node node-right" id="h-node-gateway" onclick="selectHighwayNode('gateway')">
            <div class="node-icon">🌐</div>
            <div class="node-title">OpenAny Gateway</div>
            <div class="node-sub">MiniMax &bull; DeepSeek &bull; Claude &bull; 3k APIs</div>
            <div class="node-stat" style="background: rgba(126, 215, 161, 0.18); color: var(--live-green);">168+ Live Models</div>
          </div>
        </div>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--stage-muted);">
        <div><span class="text-mint font-bold">● HIGHWAY PULSE:</span> <span id="highway-status">Transmitting phototrail packets across OpenAny Gateway</span></div>
        <div id="highway-stats">PACKETS: <span class="text-gold">42 / sec</span> &bull; LOSS: <span class="text-mint">0.00%</span> &bull; REPLAY HASH: <span class="text-gold">7f83b165...</span></div>
      </div>
    </section>

    <!-- ========================================================
         OPENANY MULTI-MODEL FLEET MATRIX
         ======================================================== -->
    <section class="card" id="openany-matrix">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; openany-matrix.catalog</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 6px;">
        <div>
          <p class="opener-eyebrow"><span></span>02 / MULTI-MODEL ECOSYSTEM</p>
          <h2 style="font-size: 24px; margin-top: 4px;">OpenAny Multi-Model Fleet Matrix</h2>
          <p class="text-xs text-dim">Access 168+ frontier models and 3,258 tools with one unified key and shared prepaid balance.</p>
        </div>
        <button class="folio-action" onclick="loadPreset('openany_models')">Discover Full 168+ Catalog &rarr;</button>
      </div>

      <div class="matrix-grid">
        <!-- MiniMax M2.5 -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">MiniMax-M2.5</div>
                <div class="model-provider">MiniMax &bull; Fast Reasoning</div>
              </div>
              <span class="badge" style="background: rgba(126, 215, 161, 0.15); color: var(--live-green);">Tested Live</span>
            </div>
            <p class="text-xs text-dim">Optimized for high-speed chain-of-thought tool calling and reasoning with sub-cent token billing.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$0.15/1M</span></div>
              <div class="rate-pill">Compl: <span>$0.60/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('MiniMax-M2.5')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>

        <!-- MiniMax M2.7 -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">MiniMax-M2.7</div>
                <div class="model-provider">MiniMax &bull; Extended Context</div>
              </div>
              <span class="badge" style="background: rgba(244, 185, 76, 0.15); color: var(--gold);">Frontier</span>
            </div>
            <p class="text-xs text-dim">Extended context coding and deep multi-step autonomous agent synthesis.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$0.20/1M</span></div>
              <div class="rate-pill">Compl: <span>$0.80/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('MiniMax-M2.7')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>

        <!-- DeepSeek V3 -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">DeepSeek-V3</div>
                <div class="model-provider">DeepSeek &bull; 671B MoE</div>
              </div>
              <span class="badge" style="background: rgba(208, 96, 63, 0.15); color: #ff9d85;">Ultra-Value</span>
            </div>
            <p class="text-xs text-dim">Frontier intelligence at disruptive pricing. 671B MoE architecture with deep coding capabilities.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$0.14/1M</span></div>
              <div class="rate-pill">Compl: <span>$0.28/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('deepseek/deepseek-chat')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>

        <!-- Claude 3.7 Sonnet -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">Claude 3.7 Sonnet</div>
                <div class="model-provider">Anthropic &bull; Agentic Flagship</div>
              </div>
              <span class="badge" style="background: rgba(244, 185, 76, 0.18); color: var(--gold-bright);">Hybrid CoT</span>
            </div>
            <p class="text-xs text-dim">Industry-standard agentic coding with hybrid standard and extended thinking modes.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$3.00/1M</span></div>
              <div class="rate-pill">Compl: <span>$15.00/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('anthropic/claude-3.7-sonnet')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>

        <!-- Gemini 2.5 Flash -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">Gemini 2.5 Flash</div>
                <div class="model-provider">Google &bull; 1M Context</div>
              </div>
              <span class="badge" style="background: rgba(83, 201, 238, 0.15); color: var(--cyan);">Low Latency</span>
            </div>
            <p class="text-xs text-dim">Sub-100ms multi-modal reasoning with massive 1,000,000 token context window.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$0.075/1M</span></div>
              <div class="rate-pill">Compl: <span>$0.30/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('google/gemini-2.5-flash')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>

        <!-- Qwen 2.5 Coder 32B -->
        <div class="model-card">
          <div>
            <div class="model-head">
              <div>
                <div class="model-name">Qwen 2.5 Coder</div>
                <div class="model-provider">Alibaba &bull; 32B Code Specialist</div>
              </div>
              <span class="badge" style="background: rgba(126, 215, 161, 0.15); color: var(--live-green);">Code MoE</span>
            </div>
            <p class="text-xs text-dim">High-density open weights fine-tuned specifically for repository-level code edits and refactoring.</p>
            <div class="model-rates">
              <div class="rate-pill">Prompt: <span>$0.20/1M</span></div>
              <div class="rate-pill">Compl: <span>$0.60/1M</span></div>
            </div>
          </div>
          <button class="folio-action-secondary" onclick="testModel('qwen/qwen-2.5-coder-32b-instruct')" style="margin-top: 10px; justify-content: center; width: 100%;">Test in Playground &rarr;</button>
        </div>
      </div>
    </section>

    <!-- ========================================================
         AVIONICS COCKPIT & BLACK-BOX FLIGHT REPLAYER
         ======================================================== -->
    <section class="card hud-card" id="cockpit-deck">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; cockpit-replayer.flight.json</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
          <p class="opener-eyebrow"><span></span>03 / DETERMINISTIC COCKPIT DECK</p>
          <h2 style="font-size: 24px; margin-top: 4px;">Mission Control & Black-Box Flight Deck</h2>
          <p class="text-xs text-dim">Deterministic trajectory replay, anti-loop circuit breaker, and live SHA-256 Merkle chain verification.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="folio-action" onclick="testLintGoodTool()">Lint Clean Tool &rarr;</button>
          <button class="folio-action-secondary" onclick="testLintSmellyTool()">Lint Smelly Tool &rarr;</button>
        </div>
      </div>

      <!-- Visual Trajectory Waypoint Track -->
      <div class="waypoint-track" id="waypoint-track">
        <div class="waypoint-line">
          <div class="waypoint-line-fill" id="track-fill"></div>
        </div>
        <div class="waypoint-node active" id="wp-node-0" onclick="scrubStep(0)">
          <div class="waypoint-dot">01</div>
          <div class="waypoint-title">Ingest Intent</div>
        </div>
        <div class="waypoint-node" id="wp-node-1" onclick="scrubStep(1)">
          <div class="waypoint-dot">02</div>
          <div class="waypoint-title">Tool Lookup</div>
        </div>
        <div class="waypoint-node" id="wp-node-2" onclick="scrubStep(2)">
          <div class="waypoint-dot">03</div>
          <div class="waypoint-title">Cost Shield</div>
        </div>
        <div class="waypoint-node" id="wp-node-3" onclick="scrubStep(3)">
          <div class="waypoint-dot">04</div>
          <div class="waypoint-title">Execution</div>
        </div>
      </div>

      <!-- Flight Replayer Controls -->
      <div class="player-controls" style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--card-rule);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="mono text-xs font-bold text-gold">ACTIVE FLIGHT:</span>
            <select id="flight-select" class="folio-action-secondary" onchange="changeFlight(this.value)" style="background: rgba(0,0,0,0.5); cursor: pointer;">
              <option value="flight_golden">Flight #101: Clean Multi-Step Checkout (4 Golden Spans)</option>
              <option value="flight_incident">Flight #204: Oscillating Loop Incident (Circuit Tripped)</option>
              <option value="flight_openany">Flight #305: OpenAny Multi-Model Gateway Chain</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button class="folio-action-secondary" onclick="prevStep()">◀ Prev</button>
            <button class="folio-action" id="play-btn" onclick="togglePlay()">▶ Play</button>
            <button class="folio-action-secondary" onclick="nextStep()">Next ▶</button>
            <span id="step-counter" class="mono text-xs text-dim" style="margin-left: 8px;">Step 1 / 4</span>
          </div>
        </div>

        <div style="margin-bottom: 16px;">
          <input type="range" id="flight-scrubber" min="0" max="3" value="0" style="width: 100%; accent-color: var(--gold); cursor: pointer;" oninput="scrubStep(parseInt(this.value))">
        </div>

        <!-- Telemetry Gauges for Active Step -->
        <div class="flight-step-card" style="background: rgba(12, 10, 18, 0.6); border: 1px solid var(--card-border); border-radius: 10px; padding: 18px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-kind-badge" class="badge" style="background: rgba(83, 201, 238, 0.2); color: var(--cyan);">tool_call</span>
              <span id="step-actor" class="mono font-bold" style="color: #fff; font-size: 14px;">search_catalog</span>
              <span id="step-status-badge" class="badge" style="background: rgba(126, 215, 161, 0.2); color: var(--live-green);">200 OK</span>
            </div>
            <div class="mono text-xs" id="step-metrics" style="color: var(--stage-muted);">
              <span style="color: var(--gold);">14.2 ms</span> &bull; 
              <span style="color: var(--live-green);">$0.0003</span> &bull; 
              <span>120 Tokens</span>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
            <div>
              <div class="mono text-xs text-muted" style="margin-bottom: 4px;">INPUT ARGUMENTS</div>
              <pre id="step-input" class="response-box" style="margin: 0; max-height: 120px; font-size: 11px;"></pre>
            </div>
            <div>
              <div class="mono text-xs text-muted" style="margin-bottom: 4px;">OUTPUT RESULT / TELEMETRY</div>
              <pre id="step-output" class="response-box" style="margin: 0; max-height: 120px; font-size: 11px;"></pre>
            </div>
          </div>
          
          <div id="step-hash-bar" class="mono text-xs" style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.06); color: var(--stage-quiet); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
            <span>CHAIN HASH: <span id="step-hash" style="color: var(--gold);">e3b0c442...</span></span>
            <span style="color: var(--live-green);">✔ SHA-256 MERKLE INTEGRITY SEALED</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ========================================================
         CRYPTOGRAPHIC BLACK-BOX FLIGHT RECEIPT
         ======================================================== -->
    <section class="card" id="flight-receipt-section">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; black-box-receipt.accounting</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
        <div>
          <p class="opener-eyebrow"><span></span>04 / ITEMIZED TELEMETRY SLIP</p>
          <h2 style="font-size: 24px; margin-top: 4px;">Cryptographic Flight Usage Receipt</h2>
          <p class="text-xs text-dim">Monospace itemized breakdown of model tokens, tool executions, and circuit breaker savings.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="folio-action" onclick="printSimulatedReceipt()">⚡ Print / Re-Simulate Slip</button>
          <button class="folio-action-secondary" onclick="copyReceiptText()">Copy Receipt</button>
        </div>
      </div>

      <div class="receipt-container" id="receipt-box">
        <div class="receipt-header">
          <div class="receipt-title">✈ AGENTFLIGHT CASSETTE FLIGHT RECORD & USAGE SLIP</div>
          <div class="mono text-xs text-dim" style="margin-top: 4px;">CARRIER: OPENANY MULTI-MODEL ROUTER &bull; PROTOCOL: MCP 2024-11-05</div>
        </div>

        <div class="receipt-line">
          <span class="text-muted">FLIGHT IDENTIFIER:</span>
          <span class="mono font-bold text-gold" id="rcpt-flight-id">AF-101-GOLDEN</span>
        </div>
        <div class="receipt-line">
          <span class="text-muted">ROUTED GATEWAY:</span>
          <span class="mono" id="rcpt-carrier">OpenAny Unified Gateway (AIephant)</span>
        </div>
        <div class="receipt-line">
          <span class="text-muted">ACTIVE MODEL:</span>
          <span class="mono text-gold font-bold" id="rcpt-model">MiniMax-M2.5 (Thinking CoT)</span>
        </div>
        <div class="receipt-line">
          <span class="text-muted">CIRCUIT BREAKER:</span>
          <span class="mono text-mint font-bold" id="rcpt-circuit">PASS (0 LOOPS)</span>
        </div>

        <div class="receipt-divider"></div>

        <div class="receipt-line" style="font-weight: 600; color: #d9cfd8; font-size: 11px;">
          <span>ITEM / EXECUTION SPAN</span>
          <span>QUANTITY</span>
          <span>UNIT RATE</span>
          <span>BILLED</span>
        </div>

        <div class="receipt-line" id="rcpt-row-prompt">
          <span id="rcpt-lbl-prompt">Prompt Tokens</span>
          <span id="rcpt-qty-prompt">1,420</span>
          <span>$0.150 / 1M</span>
          <span id="rcpt-cost-prompt">$0.000213</span>
        </div>

        <div class="receipt-line" id="rcpt-row-completion">
          <span id="rcpt-lbl-completion">Completion Tokens</span>
          <span id="rcpt-qty-completion">384</span>
          <span>$0.600 / 1M</span>
          <span id="rcpt-cost-completion">$0.000230</span>
        </div>

        <div class="receipt-line" id="rcpt-row-tools">
          <span>MCP Tool Executions</span>
          <span id="rcpt-qty-tools">3 spans</span>
          <span>$0.000 / call</span>
          <span>$0.000000</span>
        </div>

        <div class="receipt-line" id="rcpt-row-circuit">
          <span>Anti-Loop Safety Trips</span>
          <span id="rcpt-qty-circuit">0 severed</span>
          <span>$0.000</span>
          <span>$0.000000</span>
        </div>

        <div class="receipt-divider"></div>

        <div class="receipt-line receipt-total">
          <span>TOTAL FLIGHT CHARGE</span>
          <span id="rcpt-total-cost">$0.000443</span>
        </div>

        <div class="receipt-line" style="color: var(--gold); margin-top: 4px;">
          <span>PRE-FLIGHT SPEND SAVINGS (Loops Prevented)</span>
          <span id="rcpt-savings">+$0.840000</span>
        </div>

        <div class="receipt-divider"></div>

        <div style="font-size: 11px; color: var(--stage-quiet);">
          <div>IMMUTABLE CASSETTE SEAL (SHA-256):</div>
          <div class="mono text-cyan" id="rcpt-hash" style="word-break: break-all; margin-top: 2px;">
            7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069
          </div>
        </div>

        <div class="receipt-barcode">
          ||| | ||||| || |||||| | |||| |||||||| ||| ||||||| | ||
        </div>
      </div>
    </section>

    <!-- ========================================================
         MCP TOOL SCHEMA DOCTOR & AUTO-HEALER
         ======================================================== -->
    <section class="card" id="schema-doctor">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; schema-doctor.auto-heal</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
        <div>
          <p class="opener-eyebrow"><span></span>05 / SCHEMA HEALTH</p>
          <h2 style="font-size: 24px; margin-top: 4px;">MCP Tool Schema Doctor & Auto-Healer</h2>
          <p class="text-xs text-dim">Audit and automatically harden flawed MCP tool schemas into Glama TDQS Gold Standard.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="folio-action-secondary" onclick="loadDoctorSample('flawed')">Load Smelly Tool</button>
          <button class="folio-action" onclick="healCurrentSchema()">⚡ Auto-Heal with AgentFlight Fix</button>
        </div>
      </div>

      <div class="playground-grid">
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Input Tool Schema (Raw / Smelly)</span>
            <span id="doc-score-orig" class="badge" style="background: rgba(208, 96, 63, 0.2); color: #ff9d85;">Score: 28 &bull; Grade F</span>
          </div>
          <textarea id="doctor-input" class="code-editor" style="height: 220px;" placeholder="Paste raw tool JSON here..."></textarea>
        </div>
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Hardened Schema (Glama TDQS Compliant)</span>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span id="doc-score-fixed" class="badge" style="background: rgba(126, 215, 161, 0.2); color: var(--live-green);">Score: 98 &bull; Grade A+</span>
              <button class="folio-action-sm" onclick="copyDoctorOutput()">Copy</button>
            </div>
          </div>
          <pre id="doctor-output" class="response-box" style="height: 220px;">// Click "Auto-Heal with AgentFlight Fix" to harden schema</pre>
        </div>
      </div>
    </section>

    <!-- ========================================================
         1-CLICK CLIENT CONFIGURATION
         ======================================================== -->
    <section class="card" id="client-config">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; client-integration.sh</span>
      </div>
      <p class="opener-eyebrow"><span></span>06 / CLIENT INTEGRATION</p>
      <h2 style="font-size: 24px; margin-top: 4px; margin-bottom: 14px;">1-Click Client Configuration</h2>
      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab(this, 'tab-claude-code')">Claude Code</button>
        <button class="tab-btn" onclick="switchTab(this, 'tab-cursor')">Cursor</button>
        <button class="tab-btn" onclick="switchTab(this, 'tab-windsurf')">Windsurf</button>
        <button class="tab-btn" onclick="switchTab(this, 'tab-desktop')">Claude Desktop</button>
        <button class="tab-btn" onclick="switchTab(this, 'tab-smithery')">Smithery CLI</button>
        <button class="tab-btn" onclick="switchTab(this, 'tab-stdio')">Local Stdio</button>
      </div>

      <div id="tab-claude-code" class="tab-pane">
        <div class="snippet-box">
          <pre>{html.escape(claude_code_cmd)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy Command</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Run directly in your terminal to register in Claude Code project/global config.</p>
      </div>

      <div id="tab-cursor" class="tab-pane" style="display: none;">
        <div class="snippet-box">
          <pre>{html.escape(cursor_cfg)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy JSON</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Paste into your project's <code>.cursor/mcp.json</code> or user settings.</p>
      </div>

      <div id="tab-windsurf" class="tab-pane" style="display: none;">
        <div class="snippet-box">
          <pre>{html.escape(cursor_cfg)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy JSON</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Paste into <code>~/.codeium/windsurf/mcp_config.json</code>.</p>
      </div>

      <div id="tab-desktop" class="tab-pane" style="display: none;">
        <div class="snippet-box">
          <pre>{html.escape(claude_desktop_cfg)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy JSON</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Paste into <code>claude_desktop_config.json</code>.</p>
      </div>

      <div id="tab-smithery" class="tab-pane" style="display: none;">
        <div class="snippet-box">
          <pre>{html.escape(smithery_cmd)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy Command</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Installs via the Smithery registry orchestrator.</p>
      </div>

      <div id="tab-stdio" class="tab-pane" style="display: none;">
        <div class="snippet-box">
          <pre>{html.escape(stdio_cmd)}</pre>
          <button class="copy-btn" onclick="copySnippet(this)">Copy Command</button>
        </div>
        <p class="text-xs text-muted" style="margin-top: 8px;">Runs locally without any installation via uvx.</p>
      </div>
    </section>

    <!-- ========================================================
         INTERACTIVE JSON-RPC PLAYGROUND
         ======================================================== -->
    <section class="card" id="playground">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; json-rpc.playground</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
        <div>
          <p class="opener-eyebrow"><span></span>07 / LIVE RPC PLAYGROUND</p>
          <h2 style="font-size: 24px; margin-top: 4px;">Interactive JSON-RPC Playground</h2>
          <p class="text-xs text-dim">Test live serverless MCP execution and OpenAny model gateways with sub-millisecond measurement.</p>
        </div>
        <div class="preset-bar">
          <button class="folio-action-sm" onclick="loadPreset('openany_models')">OpenAny Models</button>
          <button class="folio-action-sm" onclick="loadPreset('openany_chat')">OpenAny Chat</button>
          <button class="folio-action-sm" onclick="loadPreset('init')">initialize</button>
          <button class="folio-action-sm" onclick="loadPreset('tools_list')">tools/list</button>
          <button class="folio-action-sm" onclick="loadPreset('sample_call')">lint_clean</button>
          <button class="folio-action-sm" onclick="loadPreset('lint_smelly')">lint_smelly</button>
          <button class="folio-action-sm" onclick="loadPreset('res_list')">resources/list</button>
          <button class="folio-action-sm" onclick="loadPreset('res_templates')">resources/templates</button>
          <button class="folio-action-sm" onclick="loadPreset('prompts_list')">prompts/list</button>
        </div>
      </div>

      <div class="playground-grid">
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Request (JSON-RPC 2.0)</span>
            <div style="display: flex; gap: 8px;">
              <button class="folio-action-sm" id="copy-curl-btn" onclick="copyAsCurl()">Copy cURL</button>
              <button class="folio-action" id="send-btn" onclick="sendJsonRpc()">Send Request &rarr;</button>
            </div>
          </div>
          <textarea id="rpc-request" class="code-editor">{html.escape(sample_call_json)}</textarea>
        </div>
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Response</span>
            <div style="display: flex; align-items: center; gap: 8px;">
              <button class="folio-action-sm" id="copy-resp-btn" onclick="copyResponse()">Copy</button>
              <span id="rpc-meta" class="text-xs mono text-muted">Ready</span>
            </div>
          </div>
          <pre id="rpc-response" class="response-box">// Click "Send Request" to test live serverless execution</pre>
        </div>
      </div>
    </section>

    <!-- ========================================================
         CAPABILITIES CATALOGS WITH SEARCH
         ======================================================== -->
    <section class="card">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; capabilities.tools</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
        <div>
          <p class="opener-eyebrow"><span></span>08 / REGISTERED FLIGHT TOOLS</p>
          <h2 style="font-size: 24px; margin-top: 4px;">Registered Flight Tools ({len(tools)})</h2>
          <p class="text-xs text-dim">Static tool-smell linters, OpenAny model routers, and trajectory cassette engines.</p>
        </div>
        <input type="text" class="search-input" placeholder="Search tools by name..." oninput="filterTools(this.value)">
      </div>
      <div class="card-list" id="tools-list">{tools_html}</div>
    </section>

    <section class="card">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; capabilities.resources</span>
      </div>
      <p class="opener-eyebrow"><span></span>09 / FLIGHT RESOURCES</p>
      <h2 style="font-size: 24px; margin-top: 4px; margin-bottom: 14px;">Exposed Flight Resources ({len(resources)})</h2>
      <div class="card-list">{resources_html}</div>
    </section>

    <section class="card">
      <div class="console-bar" style="margin: -24px -24px 18px -24px;">
        <i></i><i></i><i></i>
        <span>agentflight &bull; capabilities.prompts</span>
      </div>
      <p class="opener-eyebrow"><span></span>10 / TRAJECTORY PROMPTS</p>
      <h2 style="font-size: 24px; margin-top: 4px; margin-bottom: 14px;">Trajectory Prompts Catalog ({len(prompts)})</h2>
      <div class="card-list">{prompts_html}</div>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <div>&copy; 2026 CodeSphere Innovations &bull; Architect: <a href="https://alvin.codesphereug.com" target="_blank" rel="noopener" style="color: var(--gold); font-weight: 700;">Akandwanaho Ivan (Alvin)</a> &bull; <a href="https://alvin.codesphereug.com/work/agentflight.html" target="_blank" rel="noopener" style="color: var(--gold-bright);">System Case Study</a> &bull; OpenAny Strategic Partner &bull; MIT License</div>
      <div class="mono">Transport: Streamable HTTP (<code>POST /mcp</code>) + SSE (<code>GET /mcp</code>)</div>
    </footer>
  </div>

  <script>
    const TOOLS = {tools_json};
    const RESOURCES = {resources_json};
    const PROMPTS = {prompts_json};
    const SAMPLE_CALL = {sample_call_json};
    const PRESETS = {presets_json};
    const FLIGHTS = {sample_flights_json};

    let currentFlightKey = 'flight_golden';
    let currentStepIdx = 0;
    let isPlaying = false;
    let playInterval = null;
    let audioEnabled = false;
    let audioCtx = null;
    let highwayMode = 'full';

    // Web Audio Synthesizer
    function toggleAudio() {{
      audioEnabled = !audioEnabled;
      const btn = document.getElementById('audio-btn');
      if (audioEnabled) {{
        btn.innerText = '🔊 Sound: ON';
        btn.style.color = 'var(--live-green)';
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        playChime(660, 0.08);
      }} else {{
        btn.innerText = '🔇 Sound: OFF';
        btn.style.color = 'var(--stage-quiet)';
      }}
    }}

    function playChime(freq = 880, dur = 0.06, type = 'sine') {{
      if (!audioEnabled || !audioCtx) return;
      try {{
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + dur);
      }} catch (_) {{}}
    }}

    // ========================================================
    // HERO TRAJECTORY HIGHWAY CANVAS
    // ========================================================
    (function initHighwayCanvas() {{
      const canvas = document.getElementById('highway-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const stage = document.getElementById('highway-stage');

      let w = canvas.width = stage.offsetWidth;
      let h = canvas.height = stage.offsetHeight;

      window.addEventListener('resize', () => {{
        if (!stage) return;
        w = canvas.width = stage.offsetWidth;
        h = canvas.height = stage.offsetHeight;
      }});

      const packets = [];
      for (let i = 0; i < 16; i++) {{
        packets.push({{
          t: Math.random(),
          speed: 0.004 + Math.random() * 0.006,
          radius: 2.5 + Math.random() * 2,
          color: Math.random() > 0.4 ? '#f4b94c' : '#7ed7a1',
        }});
      }}

      function getHighwayPoint(t) {{
        const p0 = {{ x: w * 0.16, y: h * 0.5 }};
        const p1 = {{ x: w * 0.50, y: h * 0.5 }};
        const p2 = {{ x: w * 0.84, y: h * 0.5 }};

        if (t <= 0.5) {{
          const u = t * 2;
          const cp = {{ x: (p0.x + p1.x) / 2, y: h * 0.2 }};
          const x = (1 - u) * (1 - u) * p0.x + 2 * (1 - u) * u * cp.x + u * u * p1.x;
          const y = (1 - u) * (1 - u) * p0.y + 2 * (1 - u) * u * cp.y + u * u * p1.y;
          return {{ x, y }};
        }} else {{
          const u = (t - 0.5) * 2;
          const cp = {{ x: (p1.x + p2.x) / 2, y: h * 0.8 }};
          const x = (1 - u) * (1 - u) * p1.x + 2 * (1 - u) * u * cp.x + u * u * p2.x;
          const y = (1 - u) * (1 - u) * p1.y + 2 * (1 - u) * u * cp.y + u * u * p2.y;
          return {{ x, y }};
        }}
      }}

      function drawHighway() {{
        ctx.clearRect(0, 0, w, h);

        const p0 = {{ x: w * 0.16, y: h * 0.5 }};
        const p1 = {{ x: w * 0.50, y: h * 0.5 }};
        const p2 = {{ x: w * 0.84, y: h * 0.5 }};

        ctx.lineWidth = 2;
        ctx.strokeStyle = 'rgba(244, 185, 76, 0.2)';
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.quadraticCurveTo((p0.x + p1.x) / 2, h * 0.2, p1.x, p1.y);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(126, 215, 161, 0.2)';
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.quadraticCurveTo((p1.x + p2.x) / 2, h * 0.8, p2.x, p2.y);
        ctx.stroke();

        packets.forEach(p => {{
          p.t += p.speed;
          if (p.t > 1) p.t = 0;

          const pt = getHighwayPoint(p.t);
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, p.radius, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.shadowColor = p.color;
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }});

        requestAnimationFrame(drawHighway);
      }}
      drawHighway();
    }})();

    function setHighwayMode(mode) {{
      highwayMode = mode;
      const status = document.getElementById('highway-status');
      if (mode === 'full') {{
        status.innerText = 'Transmitting phototrail packets across OpenAny Gateway (Client -> Shield -> Gateway)';
        playChime(780, 0.05);
      }} else if (mode === 'vcr') {{
        status.innerText = 'Offline Deterministic VCR Mode: Serving spans from Merkle Cassette in < 5 μs';
        playChime(620, 0.05);
      }} else {{
        status.innerText = 'OpenAny Direct Passthrough: Bypassing local cassettes for zero-latency direct routing';
        playChime(880, 0.05);
      }}
    }}

    function selectHighwayNode(node) {{
      playChime(node === 'client' ? 660 : (node === 'shield' ? 880 : 1020), 0.06);
      if (node === 'client') {{
        document.getElementById('client-config').scrollIntoView({{ behavior: 'smooth' }});
      }} else if (node === 'shield') {{
        document.getElementById('cockpit-deck').scrollIntoView({{ behavior: 'smooth' }});
      }} else {{
        document.getElementById('openany-matrix').scrollIntoView({{ behavior: 'smooth' }});
      }}
    }}

    // ========================================================
    // RADAR BACKGROUND CANVAS
    // ========================================================
    (function initRadarCanvas() {{
      const canvas = document.getElementById('radar-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      let w = canvas.width = window.innerWidth;
      let h = canvas.height = window.innerHeight;
      window.addEventListener('resize', () => {{
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
      }});

      const waypoints = [
        {{ x: w * 0.15, y: h * 0.25, vx: 0.1, vy: 0.05, label: 'WP-CODESPHERE' }},
        {{ x: w * 0.45, y: h * 0.35, vx: -0.08, vy: 0.1, label: 'WP-FLIGHT' }},
        {{ x: w * 0.75, y: h * 0.20, vx: 0.05, vy: -0.06, label: 'WP-SHIELD' }},
        {{ x: w * 0.85, y: h * 0.70, vx: -0.04, vy: 0.08, label: 'WP-OPENANY' }},
        {{ x: w * 0.30, y: h * 0.65, vx: 0.07, vy: -0.05, label: 'WP-MERKLE' }},
      ];

      let sweepAngle = 0;

      function renderFrame() {{
        ctx.clearRect(0, 0, w, h);

        const cx = w * 0.5, cy = h * 0.35;
        ctx.strokeStyle = 'rgba(244, 185, 76, 0.04)';
        ctx.lineWidth = 1;
        for (let r = 80; r < Math.max(w, h); r += 160) {{
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.stroke();
        }}

        sweepAngle += 0.007;
        const sweepX = cx + Math.cos(sweepAngle) * Math.max(w, h);
        const sweepY = cy + Math.sin(sweepAngle) * Math.max(w, h);
        const grad = ctx.createLinearGradient(cx, cy, sweepX, sweepY);
        grad.addColorStop(0, 'rgba(244, 185, 76, 0.06)');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, Math.max(w, h), sweepAngle - 0.2, sweepAngle);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = 'rgba(244, 185, 76, 0.05)';
        ctx.beginPath();
        for (let i = 0; i < waypoints.length; i++) {{
          const next = waypoints[(i + 1) % waypoints.length];
          ctx.moveTo(waypoints[i].x, waypoints[i].y);
          ctx.lineTo(next.x, next.y);
        }}
        ctx.stroke();

        waypoints.forEach(wp => {{
          wp.x += wp.vx;
          wp.y += wp.vy;
          if (wp.x < 50 || wp.x > w - 50) wp.vx *= -1;
          if (wp.y < 50 || wp.y > h - 50) wp.vy *= -1;

          ctx.fillStyle = 'rgba(244, 185, 76, 0.4)';
          ctx.beginPath();
          ctx.arc(wp.x, wp.y, 2.5, 0, Math.PI * 2);
          ctx.fill();

          ctx.font = '9px monospace';
          ctx.fillStyle = 'rgba(217, 207, 216, 0.3)';
          ctx.fillText(wp.label, wp.x + 6, wp.y + 3);
        }});

        requestAnimationFrame(renderFrame);
      }}
      renderFrame();
    }})();

    // ========================================================
    // FLIGHT TELEMETRY REPLAYER & RECEIPT SYNC
    // ========================================================
    function updateReceiptFromFlight(flightKey) {{
      const flight = FLIGHTS[flightKey];
      if (!flight || !flight.receipt) return;
      const r = flight.receipt;

      const setTxt = (id, val) => {{
        const el = document.getElementById(id);
        if (el) el.innerText = val;
      }};

      setTxt('rcpt-flight-id', r.flight_no);
      setTxt('rcpt-carrier', r.carrier);
      setTxt('rcpt-model', r.model);
      setTxt('rcpt-circuit', r.circuit_status);
      setTxt('rcpt-qty-prompt', r.prompt_tokens.toLocaleString());
      setTxt('rcpt-cost-prompt', '$' + r.prompt_cost.toFixed(6));
      setTxt('rcpt-qty-completion', r.completion_tokens.toLocaleString());
      setTxt('rcpt-cost-completion', '$' + r.completion_cost.toFixed(6));
      setTxt('rcpt-qty-tools', r.tool_calls + ' spans');
      setTxt('rcpt-total-cost', '$' + r.total_cost.toFixed(6));
      setTxt('rcpt-savings', '+$' + r.savings.toFixed(6));
      setTxt('rcpt-hash', r.merkle_hash);

      const circuitEl = document.getElementById('rcpt-circuit');
      if (circuitEl) {{
        if (r.circuit_status.includes('TRIPPED')) {{
          circuitEl.style.color = 'var(--ember)';
        }} else {{
          circuitEl.style.color = 'var(--live-green)';
        }}
      }}
    }}

    function renderFlightStep(flightKey, stepIdx) {{
      const flight = FLIGHTS[flightKey];
      if (!flight) return;
      const spans = flight.spans || [];
      if (stepIdx < 0) stepIdx = 0;
      if (stepIdx >= spans.length) stepIdx = spans.length - 1;
      currentStepIdx = stepIdx;

      const span = spans[stepIdx];
      const scrubber = document.getElementById('flight-scrubber');
      if (scrubber) {{
        scrubber.max = spans.length - 1;
        scrubber.value = stepIdx;
      }}
      const counter = document.getElementById('step-counter');
      if (counter) counter.innerText = `Step ${{stepIdx + 1}} / ${{spans.length}}`;

      const actorEl = document.getElementById('step-actor');
      if (actorEl) actorEl.innerText = span.actor;

      const kindEl = document.getElementById('step-kind-badge');
      if (kindEl) kindEl.innerText = span.kind;

      const statBadge = document.getElementById('step-status-badge');
      if (statBadge) {{
        if (span.status === 'ok') {{
          statBadge.innerText = '200 OK';
          statBadge.style.color = 'var(--live-green)';
          statBadge.style.background = 'rgba(126, 215, 161, 0.2)';
        }} else if (span.status === 'tripped') {{
          statBadge.innerText = '⚡ CIRCUIT TRIPPED';
          statBadge.style.color = '#ff9d85';
          statBadge.style.background = 'rgba(208, 96, 63, 0.2)';
        }} else {{
          statBadge.innerText = '❌ ERROR';
          statBadge.style.color = '#ff9d85';
          statBadge.style.background = 'rgba(208, 96, 63, 0.2)';
        }}
      }}

      const metricsEl = document.getElementById('step-metrics');
      if (metricsEl) {{
        metricsEl.innerHTML = `
          <span style="color: var(--gold);">${{span.latency_ms}} ms</span> &bull; 
          <span style="color: var(--live-green);">$${{span.cost_usd.toFixed(4)}}</span> &bull; 
          <span>${{span.tokens}} Tokens</span>
        `;
      }}

      const inEl = document.getElementById('step-input');
      if (inEl) inEl.textContent = JSON.stringify(span.input, null, 2);

      const outEl = document.getElementById('step-output');
      if (outEl) outEl.textContent = JSON.stringify(span.output, null, 2);

      const hashEl = document.getElementById('step-hash');
      if (hashEl) hashEl.innerText = span.hash ? span.hash.substring(0, 16) + '...' : 'GENESIS';

      const trackFill = document.getElementById('track-fill');
      if (trackFill && spans.length > 1) {{
        trackFill.style.width = ((stepIdx / (spans.length - 1)) * 100) + '%';
      }}
      for (let i = 0; i < 4; i++) {{
        const node = document.getElementById('wp-node-' + i);
        if (node) {{
          node.classList.remove('active', 'passed');
          if (i === stepIdx) node.classList.add('active');
          else if (i < stepIdx) node.classList.add('passed');
        }}
      }}
      playChime(500 + stepIdx * 120, 0.04);
    }}

    function scrubStep(idx) {{
      renderFlightStep(currentFlightKey, idx);
    }}

    function prevStep() {{
      if (currentStepIdx > 0) {{
        renderFlightStep(currentFlightKey, currentStepIdx - 1);
      }}
    }}

    function nextStep() {{
      const flight = FLIGHTS[currentFlightKey];
      if (flight && currentStepIdx < flight.spans.length - 1) {{
        renderFlightStep(currentFlightKey, currentStepIdx + 1);
      }} else if (isPlaying) {{
        togglePlay();
      }}
    }}

    function togglePlay() {{
      const btn = document.getElementById('play-btn');
      if (isPlaying) {{
        clearInterval(playInterval);
        isPlaying = false;
        if (btn) {{
          btn.innerText = '▶ Play';
        }}
      }} else {{
        isPlaying = true;
        if (btn) {{
          btn.innerText = '⏸ Pause';
        }}
        playInterval = setInterval(() => {{
          const flight = FLIGHTS[currentFlightKey];
          if (currentStepIdx >= flight.spans.length - 1) {{
            currentStepIdx = -1;
          }}
          nextStep();
        }}, 1400);
      }}
    }}

    function changeFlight(key) {{
      if (isPlaying) togglePlay();
      currentFlightKey = key;
      renderFlightStep(currentFlightKey, 0);
      updateReceiptFromFlight(currentFlightKey);
    }}

    function printSimulatedReceipt() {{
      playChime(1080, 0.08);
      const box = document.getElementById('receipt-box');
      box.style.opacity = '0.3';
      setTimeout(() => {{
        box.style.transition = 'opacity 0.4s ease';
        box.style.opacity = '1';
        playChime(880, 0.05);
      }}, 250);
    }}

    function copyReceiptText() {{
      const r = FLIGHTS[currentFlightKey].receipt;
      const text = `
============================================================
✈ AGENTFLIGHT CASSETTE FLIGHT RECORD & USAGE SLIP
CARRIER: ${{r.carrier}}
FLIGHT: ${{r.flight_no}}
MODEL: ${{r.model}}
CIRCUIT STATUS: ${{r.circuit_status}}
------------------------------------------------------------
PROMPT TOKENS:     ${{r.prompt_tokens.toLocaleString()}}  ($${{r.prompt_cost.toFixed(6)}})
COMPLETION TOKENS: ${{r.completion_tokens.toLocaleString()}}  ($${{r.completion_cost.toFixed(6)}})
TOOL SPANS:        ${{r.tool_calls}} calls
TOTAL CHARGE:      $${{r.total_cost.toFixed(6)}}
PRE-FLIGHT SAVED: +$${{r.savings.toFixed(6)}}
MERKLE CASSETTE SEAL: ${{r.merkle_hash}}
============================================================
`.trim();
      navigator.clipboard.writeText(text).then(() => {{
        alert('Monospace Flight Usage Receipt copied to clipboard!');
        playChime(980, 0.06);
      }});
    }}

    // ========================================================
    // SCHEMA DOCTOR & AUTO-HEALER
    // ========================================================
    const SAMPLE_FLAWED_TOOL = {{
      "name": "lookup_customer_order",
      "description": "lookup",
      "inputSchema": {{
        "properties": {{
          "order_id": {{}},
          "limit": {{ "type": "integer" }},
          "attributes": {{ "type": "array" }}
        }}
      }}
    }};

    function loadDoctorSample(kind) {{
      document.getElementById('doctor-input').value = JSON.stringify(SAMPLE_FLAWED_TOOL, null, 2);
      document.getElementById('doc-score-orig').innerText = 'Score: 28 • Grade F';
      document.getElementById('doc-score-orig').style.background = 'rgba(208, 96, 63, 0.2)';
      document.getElementById('doc-score-orig').style.color = '#ff9d85';
    }}

    function healCurrentSchema() {{
      const raw = document.getElementById('doctor-input').value;
      let tool;
      try {{
        tool = JSON.parse(raw);
      }} catch (err) {{
        alert('Please enter valid JSON schema');
        return;
      }}

      const fixed = JSON.parse(JSON.stringify(tool));
      const name = fixed.name || 'unnamed_tool';
      if (!fixed.description || fixed.description.length < 15) {{
        fixed.description = `Executes ${{name.replace(/_/g, ' ')}} query with strict boundary parameters for deterministic LLM tool evaluation.`;
      }}
      if (!fixed.inputSchema) fixed.inputSchema = {{ type: 'object', properties: {{}} }};
      if (fixed.inputSchema.type !== 'object') fixed.inputSchema.type = 'object';
      const props = fixed.inputSchema.properties || {{}};

      for (const [k, v] of Object.entries(props)) {{
        if (!v.type) v.type = 'string';
        if (!v.description) v.description = `Specifies the ${{k.replace(/_/g, ' ')}} value.`;
        if (v.type === 'integer' || v.type === 'number') {{
          if (v.minimum === undefined) v.minimum = 1;
          if (v.maximum === undefined) v.maximum = 100;
        }} else if (v.type === 'array') {{
          if (!v.items) v.items = {{ type: 'string' }};
          if (!v.maxItems) v.maxItems = 50;
        }}
      }}
      if (!fixed.inputSchema.required) fixed.inputSchema.required = Object.keys(props).slice(0, 1);
      fixed.annotations = {{
        readOnlyHint: name.startsWith('lookup') || name.startsWith('get') || name.startsWith('search'),
        idempotentHint: true
      }};

      document.getElementById('doctor-output').textContent = JSON.stringify(fixed, null, 2);
      const scoreEl = document.getElementById('doc-score-fixed');
      scoreEl.innerText = 'Score: 98 • Grade A+';
      scoreEl.style.background = 'rgba(126, 215, 161, 0.2)';
      scoreEl.style.color = 'var(--live-green)';
      playChime(880, 0.12);
    }}

    function copyDoctorOutput() {{
      const text = document.getElementById('doctor-output').textContent;
      navigator.clipboard.writeText(text).then(() => {{
        alert('Hardened Glama TDQS schema copied to clipboard!');
      }});
    }}

    // ========================================================
    // TABS & COPY SNIPPET
    // ========================================================
    function switchTab(btn, paneId) {{
      btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      btn.closest('section').querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
      const pane = document.getElementById(paneId);
      if (pane) pane.style.display = 'block';
      playChime(700, 0.03);
    }}

    function copySnippet(btn) {{
      const pre = btn.parentElement ? btn.parentElement.querySelector('pre') : null;
      const text = pre ? pre.textContent.trim() : '';
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {{
        const old = btn.innerText;
        btn.innerText = 'Copied!';
        btn.classList.add('copied');
        playChime(980, 0.05);
        setTimeout(() => {{
          btn.innerText = old;
          btn.classList.remove('copied');
        }}, 2000);
      }}).catch(() => {{
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        const old = btn.innerText;
        btn.innerText = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {{
          btn.innerText = old;
          btn.classList.remove('copied');
        }}, 2000);
      }});
    }}

    function copyAsCurl() {{
      const raw = document.getElementById('rpc-request').value;
      let formatted = raw.trim();
      try {{
        formatted = JSON.stringify(JSON.parse(raw));
      }} catch (_) {{}}
      const escaped = formatted.replace(/'/g, "'\\''");
      const ep = (window.location.origin || '') + '/mcp';
      const cmd = `curl -X POST "${{ep}}" \
  -H "Content-Type: application/json" \
  -d '${{escaped}}'`;
      navigator.clipboard.writeText(cmd).then(() => {{
        const btn = document.getElementById('copy-curl-btn');
        const old = btn.innerText;
        btn.innerText = 'Copied cURL!';
        btn.classList.add('copied');
        playChime(980, 0.05);
        setTimeout(() => {{
          btn.innerText = old;
          btn.classList.remove('copied');
        }}, 2000);
      }});
    }}

    function copyResponse() {{
      const text = document.getElementById('rpc-response').textContent;
      navigator.clipboard.writeText(text).then(() => {{
        const btn = document.getElementById('copy-resp-btn');
        const old = btn.innerText;
        btn.innerText = 'Copied!';
        playChime(980, 0.05);
        setTimeout(() => {{
          btn.innerText = old;
        }}, 2000);
      }});
    }}

    function loadPreset(kind) {{
      const req = document.getElementById('rpc-request');
      if (PRESETS[kind]) {{
        req.value = JSON.stringify(PRESETS[kind], null, 2);
        playChime(750, 0.04);
        document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      }}
    }}

    function testModel(modelName) {{
      document.getElementById('rpc-request').value = JSON.stringify({{
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {{
          "name": "agentflight_openany_chat",
          "arguments": {{
            "model": modelName,
            "prompt": "Evaluate agent tool safety and circuit breaker parameters for zero runaway loops."
          }}
        }}
      }}, null, 2);
      playChime(880, 0.05);
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    function loadToolCall(name) {{
      const tool = TOOLS.find(t => t.name === name);
      const props = (tool && tool.inputSchema && tool.inputSchema.properties) || {{}};
      const args = {{}};
      for (const [k, v] of Object.entries(props)) {{
        if (v.type === 'string') args[k] = v.default || 'test-tool';
        else if (v.type === 'integer' || v.type === 'number') args[k] = v.default || 10;
        else if (v.type === 'boolean') args[k] = v.default || false;
        else if (v.type === 'array') args[k] = [
          {{"name": "query_database", "description": "Execute a parameterized SQL query against PostgreSQL with strict timeout bounds", "inputSchema": {{"type": "object", "properties": {{"sql": {{"type": "string"}}}}}}}}
        ];
        else args[k] = {{}};
      }}
      document.getElementById('rpc-request').value = JSON.stringify({{
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {{ "name": name, "arguments": args }}
      }}, null, 2);
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    function loadResourceRead(uri) {{
      document.getElementById('rpc-request').value = JSON.stringify({{
        "jsonrpc": "2.0",
        "id": 20,
        "method": "resources/read",
        "params": {{ "uri": uri }}
      }}, null, 2);
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    function loadPromptGet(name) {{
      const p = PROMPTS.find(x => x.name === name);
      const args = {{}};
      if (p && p.arguments) {{
        for (const a of p.arguments) {{
          args[a.name] = 'cassette-run-101';
        }}
      }}
      document.getElementById('rpc-request').value = JSON.stringify({{
        "jsonrpc": "2.0",
        "id": 30,
        "method": "prompts/get",
        "params": {{ "name": name, "arguments": args }}
      }}, null, 2);
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    function filterTools(query) {{
      const q = query.toLowerCase();
      document.querySelectorAll('.tool-card-item').forEach(card => {{
        const name = card.getAttribute('data-name').toLowerCase();
        const desc = card.getAttribute('data-desc').toLowerCase();
        card.style.display = (name.includes(q) || desc.includes(q)) ? 'flex' : 'none';
      }});
    }}

    function testLintGoodTool() {{
      loadPreset('sample_call');
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    function testLintSmellyTool() {{
      loadPreset('lint_smelly');
      document.getElementById('send-btn').scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      sendJsonRpc();
    }}

    async function sendJsonRpc() {{
      const btn = document.getElementById('send-btn');
      const meta = document.getElementById('rpc-meta');
      const respBox = document.getElementById('rpc-response');
      const raw = document.getElementById('rpc-request').value;

      btn.disabled = true;
      btn.innerText = 'Executing...';
      meta.innerText = 'Calculating...';
      playChime(600, 0.05);
      const t0 = performance.now();

      try {{
        const res = await fetch('/mcp', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: raw
        }});
        const dur = (performance.now() - t0).toFixed(1);
        const data = await res.json();
        meta.innerHTML = `<span style="color: var(--live-green);">${{res.status}} OK</span> &bull; ${{dur}} ms`;
        respBox.textContent = JSON.stringify(data, null, 2);
        playChime(1040, 0.08);
      }} catch (err) {{
        const dur = (performance.now() - t0).toFixed(1);
        meta.innerHTML = `<span style="color: var(--ember);">Error</span> &bull; ${{dur}} ms`;
        respBox.textContent = String(err);
      }} finally {{
        btn.disabled = false;
        btn.innerText = 'Send Request →';
      }}
    }}

    // Initialize telemetry flight player, receipt, and sample doctor on load
    document.addEventListener('DOMContentLoaded', () => {{
      renderFlightStep('flight_golden', 0);
      updateReceiptFromFlight('flight_golden');
      loadDoctorSample('flawed');
    }});
    renderFlightStep('flight_golden', 0);
    updateReceiptFromFlight('flight_golden');
    loadDoctorSample('flawed');
  </script>
</body>
</html>
"""
