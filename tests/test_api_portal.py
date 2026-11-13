"""Unit tests for the developer portal and upgraded HTTP/SSE endpoints in AgentFlight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from portal import render_developer_portal


def test_portal_html_render():
    html = render_developer_portal(
        server_name="agentflight",
        server_version="1.1.0",
        tagline="AI Agent Flight Recorder",
        endpoint_url="https://agentflight-tau.vercel.app/mcp",
        github_url="https://github.com/codesphere-u/agentflight",
        tools=[{"name": "agentflight_lint_tools", "description": "Lint tool schemas", "inputSchema": {"properties": {"tools_json": {"type": "string"}}, "required": ["tools_json"]}}],
        resources=[{"uri": "agentflight://rules/catalog", "name": "Rules Catalog", "mimeType": "application/json", "description": "Linter rules"}],
        prompts=[{"name": "lint-tool-definitions", "description": "Lint tool schemas prompt", "arguments": [{"name": "tools_json", "required": True}]}],
        sample_tool_call={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "agentflight_lint_tools", "arguments": {"tools_json": "[]"}}},
    )
    assert "<!DOCTYPE html>" in html
    assert "agentflight" in html
    assert "agentflight_lint_tools" in html
    assert "agentflight://rules/catalog" in html
    assert "lint-tool-definitions" in html
    assert "Operational" in html
    assert "claude mcp add" in html
    # OpenAny-inspired aerospace mission control & highway assertions
    assert "The Hero Trajectory Highway" in html
    assert "highway-canvas" in html
    assert "OpenAny Multi-Model Fleet Matrix" in html
    assert "MiniMax-M2.5" in html
    assert "DeepSeek-V3" in html
    assert "Cryptographic Flight Usage Receipt" in html
    assert "receipt-box" in html
    assert "AGENTFLIGHT CASSETTE FLIGHT RECORD & USAGE SLIP" in html
    assert "rcpt-total-cost" in html
    # Architect provenance and portfolio case study links
    assert "alvin.codesphereug.com/work/agentflight.html" in html
    assert "Akandwanaho Ivan (Alvin)" in html
    assert "Codesphere AI Suite" in html
    # Visual .flight.json timeline replay viewer
    assert "cassette-timeline" in html
    assert "renderCassetteTimeline" in html
    assert "SAMPLE_TIMELINE_CASSETTES" in html

