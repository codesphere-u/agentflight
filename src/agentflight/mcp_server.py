"""
agentflight.mcp_server
======================
Standards-Compliant Model Context Protocol (MCP) JSON-RPC 2.0 Server for AgentFlight.

Exposes AgentFlight capabilities over stdio or in-memory JSON-RPC 2.0:
- `agentflight_diff_cassettes` : Compare baseline vs. candidate cassettes for behavioral regressions.
- `agentflight_export_otel`    : Export a cassette into W3C TraceContext / OpenTelemetry JSON spans.
- `agentflight_lint_tools`     : Run the 10-rule MCP Tool-Smell Linter (`TS001`–`TS010`).
- `agentflight_verify_cassette`: Verify SHA-256 hash chain integrity of a cassette file.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, IO, List, Optional

from .diff import compare_cassettes
from .linter import SHOWCASE_HARDENED_MCP_TOOLS, ToolSmellLinter
from .otel_export import export_cassette_to_otel
from .recorder import FlightRecorder, verify_cassette

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "agentflight-mcp"
SERVER_VERSION = "1.1.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "agentflight_diff_cassettes",
        "description": (
            "Compare a baseline AgentFlight cassette against a candidate cassette across model "
            "or prompt upgrades to detect tool sequence divergence (Levenshtein/LCS), new tool "
            "errors, loop regressions, token/cost deltas, and structural output drift."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["baseline_path", "candidate_path"],
            "properties": {
                "baseline_path": {
                    "type": "string",
                    "description": "Path to the golden baseline .flight.json or .flight.jsonl cassette.",
                },
                "candidate_path": {
                    "type": "string",
                    "description": "Path to the candidate .flight.json or .flight.jsonl cassette.",
                },
                "similarity_threshold": {
                    "type": "number",
                    "description": "Minimum trajectory similarity threshold in [0.0, 1.0] (default 0.80).",
                },
                "max_cost_increase_pct": {
                    "type": "number",
                    "description": "Maximum allowed percentage increase in USD cost (default 50.0).",
                },
                "max_token_increase_pct": {
                    "type": "number",
                    "description": "Maximum allowed percentage increase in total tokens (default 50.0).",
                },
            },
        },
    },
    {
        "name": "agentflight_export_otel",
        "description": (
            "Convert a recorded AgentFlight cassette into W3C TraceContext / OpenTelemetry "
            "compatible JSON spans for critical-path DAG analysis and SLO monitoring in StackPulse."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["cassette_path"],
            "properties": {
                "cassette_path": {
                    "type": "string",
                    "description": "Path to the .flight.json or .flight.jsonl cassette file.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional file path where exported OTel spans JSON will be written.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Optional override for the root OpenTelemetry service_name.",
                },
            },
        },
    },
    {
        "name": "agentflight_lint_tools",
        "description": (
            "Statically analyze MCP tool schemas across all 10 ergonomics rules (TS001-TS010) "
            "and compute an Agent Ergonomics Score (0-100)."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["tools"],
            "properties": {
                "tools": {
                    "type": "array",
                    "description": "List of MCP tool schema objects to lint.",
                    "items": {"type": "object"},
                },
            },
        },
    },
    {
        "name": "agentflight_verify_cassette",
        "description": (
            "Verify the cryptographic SHA-256 hash chain integrity of a recorded .flight.json "
            "or .flight.jsonl cassette file."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["cassette_path"],
            "properties": {
                "cassette_path": {
                    "type": "string",
                    "description": "Path to the cassette file to verify.",
                },
            },
        },
    },
]


class AgentFlightMCPServer:
    """JSON-RPC 2.0 MCP Server for AgentFlight."""

    def __init__(self) -> None:
        self.linter = ToolSmellLinter()
        self.initialized = False

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return list(MCP_TOOLS)

    def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "agentflight_diff_cassettes":
            baseline_path = arguments.get("baseline_path")
            candidate_path = arguments.get("candidate_path")
            if not baseline_path or not candidate_path:
                raise ValueError("Both 'baseline_path' and 'candidate_path' are required.")
            report = compare_cassettes(
                baseline=str(baseline_path),
                candidate=str(candidate_path),
                similarity_threshold=float(arguments.get("similarity_threshold", 0.80)),
                max_cost_increase_pct=float(arguments.get("max_cost_increase_pct", 50.0)),
                max_token_increase_pct=float(arguments.get("max_token_increase_pct", 50.0)),
            )
            return self._tool_response(report.to_dict())

        if name == "agentflight_export_otel":
            cassette_path = arguments.get("cassette_path")
            if not cassette_path:
                raise ValueError("'cassette_path' is required.")
            spans = export_cassette_to_otel(
                cassette=str(cassette_path),
                service_name=arguments.get("service_name"),
                output_path=arguments.get("output_path"),
            )
            return self._tool_response({"span_count": len(spans), "spans": spans})

        if name == "agentflight_lint_tools":
            tools = arguments.get("tools")
            if not isinstance(tools, list):
                tools = SHOWCASE_HARDENED_MCP_TOOLS
            report = self.linter.lint(tools)
            return self._tool_response(report.to_dict())

        if name == "agentflight_verify_cassette":
            cassette_path = arguments.get("cassette_path")
            if not cassette_path:
                raise ValueError("'cassette_path' is required.")
            rec = FlightRecorder.load(str(cassette_path), verify=True)
            valid = verify_cassette(rec)
            return self._tool_response(
                {
                    "valid": valid,
                    "agent_id": rec.agent_id,
                    "step_count": len(rec.spans),
                    "head_hash": rec.head_hash,
                }
            )

        raise KeyError(f"Unknown tool: {name}")

    @staticmethod
    def _tool_response(payload: Dict[str, Any], is_error: bool = False) -> Dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, indent=2, sort_keys=True),
                }
            ],
            "structuredContent": payload,
            "isError": is_error,
        }

    def handle_request(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": INVALID_REQUEST, "message": "Invalid JSON-RPC 2.0 request."},
            }

        method = message.get("method")
        msg_id = message.get("id")
        is_notification = "id" not in message
        params = message.get("params") or {}

        if not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": INVALID_REQUEST, "message": "Missing or non-string method name."},
            }

        if is_notification:
            if method.startswith("notifications/"):
                self.initialized = True
            return None

        if method == "initialize":
            self.initialized = True
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {"listChanged": False}},
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.get_tool_definitions()},
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments") or {}
            if not tool_name or not isinstance(tool_name, str):
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": "Missing tool 'name' in tools/call."},
                }
            try:
                res = self._call_tool(tool_name, tool_args)
                return {"jsonrpc": "2.0", "id": msg_id, "result": res}
            except KeyError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": str(exc)},
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": self._tool_response({"error": str(exc)}, is_error=True),
                }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": METHOD_NOT_FOUND, "message": f"Method not found: {method}"},
        }

    def serve_stdio(
        self,
        stdin: Optional[IO[str]] = None,
        stdout: Optional[IO[str]] = None,
    ) -> None:
        in_stream = stdin or sys.stdin
        out_stream = stdout or sys.stdout
        for line in in_stream:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                req = json.loads(stripped)
            except json.JSONDecodeError as exc:
                err = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": PARSE_ERROR, "message": f"Parse error: {exc}"},
                }
                out_stream.write(json.dumps(err) + "\n")
                out_stream.flush()
                continue
            resp = self.handle_request(req)
            if resp is not None:
                out_stream.write(json.dumps(resp) + "\n")
                out_stream.flush()
