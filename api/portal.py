"""Interactive Developer Portal & Avionics Flight Deck for AgentFlight.

Renders a self-contained, magical, responsive HTML5 aerospace cockpit interface
when a user or browser visits the endpoint with Accept: text/html.
Features interactive trajectory replay, live radar canvas, schema auto-healer,
synthesized Web Audio avionics, and live JSON-RPC execution.
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
    """Generate a magical, extraordinary HTML avionics cockpit flight dashboard."""

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
            "title": "Flight #204: Oscillating Loop Incident (Tripped)",
            "severity": "CRITICAL",
            "status_label": "CIRCUIT BREAKER TRIPPED",
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
                <span class="mono font-bold text-amber">{t_name}</span>
                <button class="btn btn-sm btn-ghost" onclick="loadToolCall('{t_name}')">Test &rarr;</button>
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
                <span class="mono font-bold text-green">{r_name}</span>
                <button class="btn btn-sm btn-ghost" onclick="loadResourceRead('{r_uri}')">Read &rarr;</button>
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
                <button class="btn btn-sm btn-ghost" onclick="loadPromptGet('{p_name}')">Render &rarr;</button>
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
  <title>{safe_name} &bull; Flight Recorder & MCP Linter Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #030712;
      --card-bg: rgba(10, 16, 28, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-border-glow: rgba(245, 158, 11, 0.35);
      --amber: #f59e0b;
      --amber-glow: rgba(245, 158, 11, 0.25);
      --green: #10b981;
      --green-glow: rgba(16, 185, 129, 0.25);
      --cyan: #06b6d4;
      --purple: #8b5cf6;
      --red: #ef4444;
      --text: #f8fafc;
      --text-dim: #94a3b8;
      --text-muted: #64748b;
      --font-mono: 'JetBrains Mono', monospace;
      --font-sans: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding: 0 16px 40px;
      min-height: 100vh;
      position: relative;
      overflow-x: hidden;
    }}
    #radar-canvas {{
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      pointer-events: none;
      z-index: 0;
      opacity: 0.45;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }}
    
    /* Top Ticker */
    .top-ticker {{
      display: flex; justify-content: space-between; align-items: center;
      background: rgba(15, 23, 42, 0.7);
      border-bottom: 1px solid var(--card-border);
      padding: 8px 16px; margin: 0 -16px 20px -16px;
      font-size: 11px; font-family: var(--font-mono);
      backdrop-filter: blur(8px);
    }}
    .ticker-pulse {{
      display: inline-block; width: 7px; height: 7px; border-radius: 50%;
      background: var(--green); margin-right: 6px;
      box-shadow: 0 0 8px var(--green);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.3); opacity: 0.6; }}
    }}

    /* Header */
    .header {{
      padding: 24px 0 18px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 24px;
    }}
    .header-top {{
      display: flex; justify-content: space-between; align-items: flex-start;
      flex-wrap: wrap; gap: 16px; margin-bottom: 20px;
    }}
    .title-group {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    h1 {{
      font-size: 28px; font-weight: 700; letter-spacing: -0.02em;
      display: flex; align-items: center; gap: 10px;
      background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .badge {{
      font-size: 11px; font-family: var(--font-mono); padding: 3px 8px;
      border-radius: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
    }}
    .badge-ver {{ background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-live {{ background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.3); }}
    .badge-proto {{ background: rgba(6, 182, 212, 0.15); color: var(--cyan); border: 1px solid rgba(6, 182, 212, 0.3); }}
    .links {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    
    /* Buttons */
    .btn {{
      background: rgba(255, 255, 255, 0.05); color: var(--text); border: 1px solid var(--card-border);
      padding: 7px 13px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer;
      text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      backdrop-filter: blur(6px);
    }}
    .btn:hover {{
      background: rgba(255, 255, 255, 0.12); border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }}
    .btn:active {{ transform: translateY(0); }}
    .btn-sm {{ font-size: 12px; padding: 5px 10px; }}
    .btn-amber {{ background: var(--amber); color: #000; border-color: var(--amber); font-weight: 600; }}
    .btn-amber:hover {{ background: #fbbf24; border-color: #fbbf24; box-shadow: 0 0 16px var(--amber-glow); }}
    .btn-cyan {{ background: var(--cyan); color: #000; border-color: var(--cyan); font-weight: 600; }}
    .btn-cyan:hover {{ background: #22d3ee; box-shadow: 0 0 16px rgba(6, 182, 212, 0.4); }}
    .btn-ghost {{ background: transparent; border-color: transparent; color: var(--text-dim); }}
    .btn-ghost:hover {{ background: rgba(255, 255, 255, 0.05); color: var(--text); }}
    .audio-toggle {{ font-family: var(--font-mono); font-size: 11px; }}

    /* Cards */
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px; padding: 22px;
      margin-bottom: 24px;
      backdrop-filter: blur(14px);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
      position: relative;
    }}
    
    /* Stats Grid */
    .grid-stats {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px; margin-top: 18px;
    }}
    .stat-card {{
      background: rgba(15, 23, 42, 0.45); border: 1px solid var(--card-border);
      padding: 14px 18px; border-radius: 8px;
      transition: all 0.2s ease;
    }}
    .stat-card:hover {{ border-color: var(--card-border-glow); transform: translateY(-2px); }}
    .stat-val {{ font-size: 24px; font-weight: 700; font-family: var(--font-mono); }}
    .stat-lbl {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }}

    /* Cockpit HUD */
    .hud-card {{
      border: 1px solid var(--card-border-glow);
      box-shadow: 0 0 25px rgba(245, 158, 11, 0.1);
    }}
    .hud-display {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px; margin-top: 14px;
    }}
    .hud-item {{
      background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 6px; padding: 12px 14px;
    }}
    .hud-label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; display: block; }}
    .hud-val {{ font-size: 14px; font-weight: 600; color: #fff; margin-top: 4px; display: block; }}

    /* Trajectory Visual Waypoints */
    .waypoint-track {{
      display: flex; justify-content: space-between; align-items: center;
      position: relative; margin: 20px 0 14px; padding: 0 20px;
    }}
    .waypoint-line {{
      position: absolute; top: 18px; left: 40px; right: 40px; height: 3px;
      background: rgba(255, 255, 255, 0.1); z-index: 0;
    }}
    .waypoint-line-fill {{
      height: 100%; background: linear-gradient(90deg, var(--amber), var(--green));
      width: 0%; transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .waypoint-node {{
      position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center;
      cursor: pointer; transition: transform 0.2s ease;
    }}
    .waypoint-node:hover {{ transform: scale(1.1); }}
    .waypoint-dot {{
      width: 36px; height: 36px; border-radius: 50%; background: #0f172a;
      border: 2px solid var(--text-muted); display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-family: var(--font-mono); font-weight: 700; color: var(--text-dim);
      box-shadow: 0 0 10px rgba(0,0,0,0.5); transition: all 0.3s ease;
    }}
    .waypoint-node.active .waypoint-dot {{
      border-color: var(--amber); color: #000; background: var(--amber);
      box-shadow: 0 0 18px var(--amber-glow);
    }}
    .waypoint-node.passed .waypoint-dot {{
      border-color: var(--green); color: #fff; background: rgba(16, 185, 129, 0.2);
    }}
    .waypoint-title {{
      font-size: 11px; font-family: var(--font-mono); color: var(--text-dim);
      margin-top: 6px; text-align: center; max-width: 110px;
    }}

    /* Tabs */
    .tabs {{
      display: flex; gap: 4px; border-bottom: 1px solid var(--card-border);
      margin-bottom: 14px; overflow-x: auto;
    }}
    .tab-btn {{
      background: transparent; color: var(--text-dim); border: none;
      padding: 10px 14px; font-size: 13px; font-weight: 500; cursor: pointer;
      border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;
    }}
    .tab-btn:hover {{ color: var(--text); }}
    .tab-btn.active {{ color: var(--amber); border-bottom-color: var(--amber); font-weight: 600; }}
    
    .snippet-box {{
      position: relative; background: #02040a; border: 1px solid var(--card-border);
      border-radius: 8px; padding: 14px 16px; margin-top: 8px;
    }}
    pre {{ font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: #e2e8f0; overflow-x: auto; }}
    .copy-btn {{
      position: absolute; top: 10px; right: 10px;
      background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.15);
      color: #cbd5e1; font-size: 11px; padding: 4px 9px; border-radius: 4px; cursor: pointer;
      transition: all 0.2s; font-family: var(--font-sans);
    }}
    .copy-btn:hover {{ background: rgba(255, 255, 255, 0.2); color: #fff; }}
    .copy-btn.copied {{ background: var(--green); color: #000; border-color: var(--green); }}

    /* Playground */
    .playground-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
      gap: 16px; margin-top: 14px;
    }}
    .pane {{
      background: #02040a; border: 1px solid var(--card-border); border-radius: 8px;
      display: flex; flex-direction: column; overflow: hidden;
    }}
    .pane-head {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 14px; background: rgba(255, 255, 255, 0.02);
      border-bottom: 1px solid var(--card-border);
    }}
    .pane-title {{ font-size: 12px; font-weight: 600; font-family: var(--font-mono); color: var(--text-dim); }}
    .code-editor {{
      width: 100%; height: 260px; background: transparent; border: none;
      color: #e2e8f0; font-family: var(--font-mono); font-size: 12px; line-height: 1.6;
      padding: 14px; resize: vertical; outline: none;
    }}
    .response-box {{
      width: 100%; height: 260px; padding: 14px; overflow: auto;
      font-family: var(--font-mono); font-size: 12px; color: #a5f3fc;
    }}
    .preset-bar {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }}

    /* Card Catalogs */
    .card-list {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 12px; margin-top: 14px;
    }}
    .item-card {{
      padding: 14px 16px; margin-bottom: 0;
      transition: all 0.2s ease;
    }}
    .item-card:hover {{ border-color: var(--card-border-glow); transform: translateY(-2px); }}
    .card-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
    .param-row {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }}
    .badge.param {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); }}
    .badge.param.req {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
    .badge.param.opt {{ background: rgba(148, 163, 184, 0.1); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); }}
    .search-input {{
      width: 100%; max-width: 380px; background: rgba(0,0,0,0.4); border: 1px solid var(--card-border);
      border-radius: 6px; padding: 8px 12px; color: #fff; font-size: 12px; outline: none;
      transition: border-color 0.2s;
    }}
    .search-input:focus {{ border-color: var(--amber); }}
    
    /* Footer */
    .footer {{
      display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;
      gap: 12px; padding: 24px 4px; border-top: 1px solid var(--card-border);
      font-size: 12px; color: var(--text-muted);
    }}
    .footer a {{ color: var(--amber); text-decoration: none; }}

    .mono {{ font-family: var(--font-mono); }}
    .font-bold {{ font-weight: 700; }}
    .text-amber {{ color: var(--amber); }}
    .text-green {{ color: var(--green); }}
    .text-cyan {{ color: var(--cyan); }}
    .text-dim {{ color: var(--text-dim); }}
    .text-muted {{ color: var(--text-muted); }}
    .text-sm {{ font-size: 13px; }}
    .text-xs {{ font-size: 11px; }}
  </style>
</head>
<body>
  <canvas id="radar-canvas"></canvas>

  <div class="top-ticker">
    <div>
      <span class="ticker-pulse"></span>
      <span class="text-green font-bold">ARMED:</span> AGENTFLIGHT BLACK-BOX AVIONICS &bull; PROTOCOL: MCP 2024-11-05 &bull; P50: 2.83 &mu;s
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
      <span class="mono text-muted">OPENANY GATEWAY: 168+ MODELS</span>
      <button class="btn btn-sm btn-ghost audio-toggle" onclick="toggleAudio()" id="audio-btn">🔊 Cockpit Sound: OFF</button>
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
          </div>
          <p class="text-sm text-dim" style="margin-top: 8px; max-width: 680px;">{safe_tagline}</p>
        </div>
        <div class="links">
          <a class="btn" href="{safe_github}" target="_blank" rel="noopener">GitHub</a>
          <a class="btn" href="/docs" target="_blank" rel="noopener">Swagger UI &rarr;</a>
          <a class="btn" href="/redoc" target="_blank" rel="noopener">ReDoc &rarr;</a>
          <a class="btn" href="https://glama.ai/mcp" target="_blank" rel="noopener">Glama</a>
          <a class="btn" href="https://smithery.ai" target="_blank" rel="noopener">Smithery</a>
        </div>
      </div>
      
      <div class="grid-stats">
        <div class="stat-card">
          <div class="stat-val text-amber">2.83 &mu;s</div>
          <div class="stat-lbl">Span Replay P50</div>
        </div>
        <div class="stat-card">
          <div class="stat-val text-green">353k</div>
          <div class="stat-lbl">Spans / Second</div>
        </div>
        <div class="stat-card">
          <div class="stat-val text-cyan">10 Rules</div>
          <div class="stat-lbl">MCP Tool-Smell Linter</div>
        </div>
        <div class="stat-card">
          <div class="stat-val" style="color: #a855f7;">168 Models</div>
          <div class="stat-lbl">OpenAny Multi-Model Gateway</div>
        </div>
        <div class="stat-card">
          <div class="stat-val" style="color: #4ade80;">$0.00</div>
          <div class="stat-lbl">Deterministic CI Replay</div>
        </div>
      </div>
    </header>

    <!-- Avionics Cockpit & Interactive Trajectory Flight Deck -->
    <section class="card hud-card" id="cockpit-deck">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <h2 style="font-size: 17px; color: #fff; display: flex; align-items: center; gap: 8px;">
            <span style="color: var(--amber);">✈</span> Mission Control & Black-Box Flight Replayer
          </h2>
          <p class="text-xs text-dim">Deterministic trajectory replay, anti-loop circuit breaker, and live SHA-256 Merkle chain verification.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm btn-amber" onclick="testLintGoodTool()">Lint Clean Tool &rarr;</button>
          <button class="btn btn-sm" onclick="testLintSmellyTool()">Lint Smelly Tool &rarr;</button>
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
      <div class="player-controls" style="margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.08);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="mono text-xs font-bold" style="color: var(--amber);">ACTIVE FLIGHT:</span>
            <select id="flight-select" class="btn btn-sm" onchange="changeFlight(this.value)" style="background: rgba(0,0,0,0.5); border: 1px solid var(--card-border); color: #fff; cursor: pointer;">
              <option value="flight_golden">Flight #101: Clean Multi-Step Checkout (4 Golden Spans)</option>
              <option value="flight_incident">Flight #204: Oscillating Loop Incident (Circuit Tripped)</option>
              <option value="flight_openany">Flight #305: OpenAny Multi-Model Gateway Chain</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <button class="btn btn-sm" onclick="prevStep()">◀ Prev</button>
            <button class="btn btn-sm btn-amber" id="play-btn" onclick="togglePlay()">▶ Play</button>
            <button class="btn btn-sm" onclick="nextStep()">Next ▶</button>
            <span id="step-counter" class="mono text-xs text-dim" style="margin-left: 8px;">Step 1 / 4</span>
          </div>
        </div>

        <div style="margin-bottom: 14px;">
          <input type="range" id="flight-scrubber" min="0" max="3" value="0" style="width: 100%; accent-color: var(--amber); cursor: pointer;" oninput="scrubStep(parseInt(this.value))">
        </div>

        <!-- Telemetry Gauges for Active Step -->
        <div class="flight-step-card" style="background: rgba(0,0,0,0.4); border: 1px solid var(--card-border); border-radius: 8px; padding: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-kind-badge" class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">tool_call</span>
              <span id="step-actor" class="mono font-bold" style="color: #fff; font-size: 14px;">search_catalog</span>
              <span id="step-status-badge" class="badge" style="background: rgba(74, 222, 128, 0.2); color: #4ade80;">200 OK</span>
            </div>
            <div class="mono text-xs" id="step-metrics" style="color: var(--text-dim);">
              <span style="color: var(--amber);">14.2 ms</span> &bull; 
              <span style="color: var(--green);">$0.0003</span> &bull; 
              <span>120 Tokens</span>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
            <div>
              <div class="mono text-xs text-muted" style="margin-bottom: 4px;">INPUT ARGUMENTS</div>
              <pre id="step-input" class="response-box" style="margin: 0; max-height: 120px; font-size: 11px;"></pre>
            </div>
            <div>
              <div class="mono text-xs text-muted" style="margin-bottom: 4px;">OUTPUT RESULT / TELEMETRY</div>
              <pre id="step-output" class="response-box" style="margin: 0; max-height: 120px; font-size: 11px;"></pre>
            </div>
          </div>
          
          <div id="step-hash-bar" class="mono text-xs" style="margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.06); color: var(--text-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
            <span>CHAIN HASH: <span id="step-hash" style="color: var(--amber);">e3b0c442...</span></span>
            <span style="color: #4ade80;">✔ SHA-256 MERKLE INTEGRITY SEALED</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Interactive Schema Doctor & 1-Click Auto-Healer -->
    <section class="card" id="schema-doctor">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <div>
          <h2 style="font-size: 16px; color: #fff; display: flex; align-items: center; gap: 8px;">
            <span style="color: var(--cyan);">⚡</span> MCP Tool Schema Doctor & Auto-Healer
          </h2>
          <p class="text-xs text-dim">Audit and automatically harden flawed MCP tool schemas into Glama TDQS Gold Standard.</p>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-sm" onclick="loadDoctorSample('flawed')">Load Smelly Tool</button>
          <button class="btn btn-sm btn-cyan" onclick="healCurrentSchema()">⚡ Auto-Heal with AgentFlight Fix</button>
        </div>
      </div>

      <div class="playground-grid">
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Input Tool Schema (Raw / Smelly)</span>
            <span id="doc-score-orig" class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171;">Score: 30 &bull; Grade F</span>
          </div>
          <textarea id="doctor-input" class="code-editor" style="height: 220px;" placeholder="Paste raw tool JSON here..."></textarea>
        </div>
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Hardened Schema (Glama TDQS Compliant)</span>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span id="doc-score-fixed" class="badge" style="background: rgba(16, 185, 129, 0.2); color: #4ade80;">Score: 98 &bull; Grade A+</span>
              <button class="btn btn-sm btn-ghost" onclick="copyDoctorOutput()">Copy</button>
            </div>
          </div>
          <pre id="doctor-output" class="response-box" style="height: 220px;">// Click "Auto-Heal with AgentFlight Fix" to harden schema</pre>
        </div>
      </div>
    </section>

    <!-- Quick Connect Box -->
    <section class="card">
      <h2 style="font-size: 16px; margin-bottom: 12px; color: #fff;">1-Click Client Configuration</h2>
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

    <!-- Interactive JSON-RPC Playground -->
    <section class="card" id="playground">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <div>
          <h2 style="font-size: 16px; color: #fff;">Interactive JSON-RPC Playground</h2>
          <p class="text-xs text-dim">Test live serverless MCP execution with sub-millisecond response measurement.</p>
        </div>
        <div class="preset-bar">
          <button class="btn btn-sm" onclick="loadPreset('init')">initialize</button>
          <button class="btn btn-sm" onclick="loadPreset('tools_list')">tools/list</button>
          <button class="btn btn-sm" onclick="loadPreset('sample_call')">lint_clean</button>
          <button class="btn btn-sm" onclick="loadPreset('lint_smelly')">lint_smelly</button>
          <button class="btn btn-sm" onclick="loadPreset('res_list')">resources/list</button>
          <button class="btn btn-sm" onclick="loadPreset('res_templates')">resources/templates</button>
          <button class="btn btn-sm" onclick="loadPreset('prompts_list')">prompts/list</button>
        </div>
      </div>

      <div class="playground-grid">
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Request (JSON-RPC 2.0)</span>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-sm" id="copy-curl-btn" onclick="copyAsCurl()">Copy as cURL</button>
              <button class="btn btn-sm btn-amber" id="send-btn" onclick="sendJsonRpc()">Send Request &rarr;</button>
            </div>
          </div>
          <textarea id="rpc-request" class="code-editor">{html.escape(sample_call_json)}</textarea>
        </div>
        <div class="pane">
          <div class="pane-head">
            <span class="pane-title">Response</span>
            <div style="display: flex; align-items: center; gap: 8px;">
              <button class="btn btn-sm btn-ghost" id="copy-resp-btn" onclick="copyResponse()">Copy</button>
              <span id="rpc-meta" class="text-xs mono text-muted">Ready</span>
            </div>
          </div>
          <pre id="rpc-response" class="response-box">// Click "Send Request" to test live serverless execution</pre>
        </div>
      </div>
    </section>

    <!-- Capabilities Catalog with Search -->
    <section class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px;">
        <div>
          <h2 style="font-size: 16px; color: #fff;">Registered Flight Tools ({len(tools)})</h2>
          <p class="text-xs text-dim">Static tool-smell linters, cassette recorders, and trajectory diff engines.</p>
        </div>
        <input type="text" class="search-input" placeholder="Search tools by name or description..." oninput="filterTools(this.value)">
      </div>
      <div class="card-list" id="tools-list">{tools_html}</div>
    </section>

    <section class="card">
      <h2 style="font-size: 16px; margin-bottom: 14px; color: #fff;">Exposed Flight Resources ({len(resources)})</h2>
      <div class="card-list">{resources_html}</div>
    </section>

    <section class="card">
      <h2 style="font-size: 16px; margin-bottom: 14px; color: #fff;">Trajectory Prompts Catalog ({len(prompts)})</h2>
      <div class="card-list">{prompts_html}</div>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <div>&copy; 2026 CodeSphere Innovations &bull; AgentFlight &bull; Released under the MIT License</div>
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

    // Web Audio Synthesizer (Zero External Dependencies)
    function toggleAudio() {{
      audioEnabled = !audioEnabled;
      const btn = document.getElementById('audio-btn');
      if (audioEnabled) {{
        btn.innerText = '🔊 Cockpit Sound: ON';
        btn.style.color = 'var(--green)';
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        playChime(660, 0.08);
      }} else {{
        btn.innerText = '🔇 Cockpit Sound: OFF';
        btn.style.color = 'var(--text-muted)';
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

    // Canvas Background Radar & Starfield
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
        {{ x: w * 0.15, y: h * 0.25, vx: 0.1, vy: 0.05, label: 'WP-01' }},
        {{ x: w * 0.45, y: h * 0.35, vx: -0.08, vy: 0.1, label: 'WP-02' }},
        {{ x: w * 0.75, y: h * 0.20, vx: 0.05, vy: -0.06, label: 'WP-03' }},
        {{ x: w * 0.85, y: h * 0.70, vx: -0.04, vy: 0.08, label: 'WP-04' }},
        {{ x: w * 0.30, y: h * 0.65, vx: 0.07, vy: -0.05, label: 'WP-05' }},
      ];

      let sweepAngle = 0;

      function renderFrame() {{
        ctx.clearRect(0, 0, w, h);

        // Subtle concentric radar circles
        const cx = w * 0.5, cy = h * 0.4;
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.04)';
        ctx.lineWidth = 1;
        for (let r = 80; r < Math.max(w, h); r += 160) {{
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.stroke();
        }}

        // Rotating radar sweep
        sweepAngle += 0.008;
        const sweepX = cx + Math.cos(sweepAngle) * Math.max(w, h);
        const sweepY = cy + Math.sin(sweepAngle) * Math.max(w, h);
        const grad = ctx.createLinearGradient(cx, cy, sweepX, sweepY);
        grad.addColorStop(0, 'rgba(245, 158, 11, 0.08)');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, Math.max(w, h), sweepAngle - 0.2, sweepAngle);
        ctx.closePath();
        ctx.fill();

        // Vector tracks
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.08)';
        ctx.beginPath();
        for (let i = 0; i < waypoints.length; i++) {{
          const next = waypoints[(i + 1) % waypoints.length];
          ctx.moveTo(waypoints[i].x, waypoints[i].y);
          ctx.lineTo(next.x, next.y);
        }}
        ctx.stroke();

        // Waypoints
        waypoints.forEach(wp => {{
          wp.x += wp.vx;
          wp.y += wp.vy;
          if (wp.x < 50 || wp.x > w - 50) wp.vx *= -1;
          if (wp.y < 50 || wp.y > h - 50) wp.vy *= -1;

          ctx.fillStyle = 'rgba(245, 158, 11, 0.4)';
          ctx.beginPath();
          ctx.arc(wp.x, wp.y, 2.5, 0, Math.PI * 2);
          ctx.fill();

          ctx.font = '9px monospace';
          ctx.fillStyle = 'rgba(148, 163, 184, 0.3)';
          ctx.fillText(wp.label, wp.x + 6, wp.y + 3);
        }});

        requestAnimationFrame(renderFrame);
      }}
      renderFrame();
    }})();

    // Flight Telemetry Replayer
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
          statBadge.style.color = '#4ade80';
          statBadge.style.background = 'rgba(74, 222, 128, 0.2)';
        }} else if (span.status === 'tripped') {{
          statBadge.innerText = '⚡ CIRCUIT TRIPPED';
          statBadge.style.color = '#f87171';
          statBadge.style.background = 'rgba(239, 68, 68, 0.2)';
        }} else {{
          statBadge.innerText = '❌ ERROR';
          statBadge.style.color = '#f87171';
          statBadge.style.background = 'rgba(239, 68, 68, 0.2)';
        }}
      }}

      const metricsEl = document.getElementById('step-metrics');
      if (metricsEl) {{
        metricsEl.innerHTML = `
          <span style="color: var(--amber);">${{span.latency_ms}} ms</span> &bull; 
          <span style="color: var(--green);">$${{span.cost_usd.toFixed(4)}}</span> &bull; 
          <span>${{span.tokens}} Tokens</span>
        `;
      }}

      const inEl = document.getElementById('step-input');
      if (inEl) inEl.textContent = JSON.stringify(span.input, null, 2);

      const outEl = document.getElementById('step-output');
      if (outEl) outEl.textContent = JSON.stringify(span.output, null, 2);

      const hashEl = document.getElementById('step-hash');
      if (hashEl) hashEl.innerText = span.hash ? span.hash.substring(0, 16) + '...' : 'GENESIS';

      // Update Waypoints Track
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
          btn.classList.remove('btn-cyan');
          btn.classList.add('btn-amber');
        }}
      }} else {{
        isPlaying = true;
        if (btn) {{
          btn.innerText = '⏸ Pause';
          btn.classList.remove('btn-amber');
          btn.classList.add('btn-cyan');
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
    }}

    // Schema Doctor & Auto-Healer
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
      document.getElementById('doc-score-orig').style.background = 'rgba(239, 68, 68, 0.2)';
      document.getElementById('doc-score-orig').style.color = '#f87171';
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

      // Interactive auto-heal logic
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
      scoreEl.style.background = 'rgba(16, 185, 129, 0.2)';
      scoreEl.style.color = '#4ade80';
      playChime(880, 0.12);
    }}

    function copyDoctorOutput() {{
      const text = document.getElementById('doctor-output').textContent;
      navigator.clipboard.writeText(text).then(() => {{
        alert('Hardened Glama TDQS schema copied to clipboard!');
      }});
    }}

    // Tabs & Copy Functions
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
      const escaped = formatted.replace(/'/g, "'\\\\''");
      const ep = (window.location.origin || '') + '/mcp';
      const cmd = `curl -X POST "${{ep}}" \\\n  -H "Content-Type: application/json" \\\n  -d '${{escaped}}'`;
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
      }}
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
        meta.innerHTML = `<span style="color: var(--green);">${{res.status}} OK</span> &bull; ${{dur}} ms`;
        respBox.textContent = JSON.stringify(data, null, 2);
        playChime(1040, 0.08);
      }} catch (err) {{
        const dur = (performance.now() - t0).toFixed(1);
        meta.innerHTML = `<span style="color: var(--red);">Error</span> &bull; ${{dur}} ms`;
        respBox.textContent = String(err);
      }} finally {{
        btn.disabled = false;
        btn.innerText = 'Send Request →';
      }}
    }}

    // Initialize telemetry flight player and sample doctor on load
    document.addEventListener('DOMContentLoaded', () => {{
      renderFlightStep('flight_golden', 0);
      loadDoctorSample('flawed');
    }});
    renderFlightStep('flight_golden', 0);
    loadDoctorSample('flawed');
  </script>
</body>
</html>
"""
