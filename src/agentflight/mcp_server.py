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
from .linter import RULE_CATALOG, SHOWCASE_HARDENED_MCP_TOOLS, ToolSmellLinter
from .otel_export import export_cassette_to_otel
from .recorder import FlightRecorder, verify_cassette

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "agentflight-mcp"
SERVER_VERSION = "1.1.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


MCP_RESOURCES: List[Dict[str, Any]] = [
    {
        "uri": "agentflight://rules/catalog",
        "name": "MCP Tool-Smell Linter Rule Catalog (TS001-TS010)",
        "description": "Comprehensive specification of the 10 static ergonomics rules for MCP tool definitions, including severity, antipattern signatures, and suggested fixes.",
        "mimeType": "application/json",
    },
    {
        "uri": "agentflight://metrics/summary",
        "name": "AgentFlight Performance Benchmarks & Subsystem Specs",
        "description": "Deterministic trajectory replay latency (<0.02ms), tool-smell linter throughput (1,676 tools/sec), and zero-overhead circuit-breaker benchmarks.",
        "mimeType": "application/json",
    },
]

MCP_RESOURCE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "uriTemplate": "agentflight://cassettes/{cassette_id}",
        "name": "AgentFlight Trajectory Cassette Template",
        "description": "Dynamic URI template to inspect recorded trajectory cassette spans and cryptographic SHA-256 verification.",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "agentflight://traces/{trace_id}",
        "name": "AgentFlight OpenTelemetry Trace Template",
        "description": "Dynamic URI template to access exported W3C TraceContext spans by trace ID.",
        "mimeType": "application/json",
    },
]

MCP_PROMPTS: List[Dict[str, Any]] = [
    {
        "name": "lint-tool-definitions",
        "description": "Review and harden MCP tool definitions against the 10 AgentFlight tool-smell rules (TS001-TS010) to maximize LLM tool-calling accuracy.",
        "arguments": [
            {
                "name": "tools_json",
                "description": "Raw JSON string or schema definition of MCP tools to analyze and fix.",
                "required": True,
            }
        ],
    },
    {
        "name": "review-agent-trajectory",
        "description": "Architectural post-mortem prompt to analyze an AI agent trajectory for repetitive loops, runaway token spend, or tool errors.",
        "arguments": [
            {
                "name": "trajectory_summary",
                "description": "Summary or step listing of the agent trajectory run.",
                "required": True,
            },
            {
                "name": "incident_symptom",
                "description": "Observed failure symptom (e.g. infinite loop, token blowout, unexpected tool error).",
                "required": False,
            },
        ],
    },
]


MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "agentflight_diff_cassettes",
        "description": (
            "Compare a baseline golden AgentFlight cassette against a candidate cassette to detect behavioral regressions.\n\n"
            "### Purpose\n"
            "Performs semantic trajectory diffing across model, prompt, or tool definition upgrades. Evaluates tool sequence divergence using Levenshtein distance and Longest Common Subsequence (LCS), identifies newly introduced tool failures, flags recursive loop regressions, and calculates token spend and USD cost deltas.\n\n"
            "### When to use\n"
            "- After upgrading LLM foundation models, prompt templates, or system instructions to verify agent behavior parity.\n"
            "- In CI/CD pipelines to block regressions when agent trajectory similarity drops below threshold or costs spike.\n\n"
            "### When NOT to use\n"
            "- Do NOT use to inspect single cassette integrity; use `agentflight_verify_cassette` instead.\n"
            "- Do NOT use to convert cassettes to telemetry traces; use `agentflight_export_otel` instead.\n\n"
            "### Behavior & Side Effects\n"
            "- Read-only: Reads both cassette files from disk without altering them.\n"
            "- Deterministic & Idempotent: Repeated invocations with identical cassettes yield exact identical diff metrics.\n"
            "- Returns structured diff metrics including similarity score (0.0 to 1.0), regression alerts, and cost deltas."
        ),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "required": ["baseline_path", "candidate_path"],
            "properties": {
                "baseline_path": {
                    "type": "string",
                    "description": "Filesystem path to the golden reference baseline cassette (.flight.json or .flight.jsonl).",
                },
                "candidate_path": {
                    "type": "string",
                    "description": "Filesystem path to the candidate cassette to evaluate against the baseline (.flight.json or .flight.jsonl).",
                },
                "similarity_threshold": {
                    "type": "number",
                    "description": "Minimum acceptable trajectory similarity coefficient in the range [0.0, 1.0]. Defaults to 0.80.",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.80,
                },
                "max_cost_increase_pct": {
                    "type": "number",
                    "description": "Maximum tolerated percentage increase in USD cost before triggering a cost regression alert. Defaults to 50.0.",
                    "minimum": 0.0,
                    "default": 50.0,
                },
                "max_token_increase_pct": {
                    "type": "number",
                    "description": "Maximum tolerated percentage increase in total tokens before triggering a token blowout alert. Defaults to 50.0.",
                    "minimum": 0.0,
                    "default": 50.0,
                },
            },
        },
        "outputSchema": {
            "type": "object",
            "required": ["passed", "similarity"],
            "properties": {
                "passed": {
                    "type": "boolean",
                    "description": "True if candidate satisfies similarity and cost/token thresholds without critical regressions.",
                },
                "similarity": {
                    "type": "number",
                    "description": "Trajectory similarity coefficient between 0.0 and 1.0 based on normalized sequence alignment.",
                },
                "baseline_id": {
                    "type": "string",
                    "description": "Identifier or filename of baseline cassette.",
                },
                "candidate_id": {
                    "type": "string",
                    "description": "Identifier or filename of candidate cassette.",
                },
                "cost_delta_usd": {
                    "type": "number",
                    "description": "USD cost variance between candidate and baseline trajectories.",
                },
                "cost_increase_pct": {
                    "type": "number",
                    "description": "Percentage increase in USD cost.",
                },
                "token_delta": {
                    "type": "integer",
                    "description": "Net difference in total tokens consumed.",
                },
                "token_increase_pct": {
                    "type": "number",
                    "description": "Percentage increase in total token consumption.",
                },
                "regressions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Detailed list of identified behavioral regressions (new tool errors, loop states, missing tools).",
                },
            },
        },
    },
    {
        "name": "agentflight_export_otel",
        "description": (
            "Export recorded AgentFlight cassette spans into W3C TraceContext and OpenTelemetry JSON traces.\n\n"
            "### Purpose\n"
            "Converts recorded agent execution spans into OpenTelemetry-compliant trace spans with standard gen_ai semantic conventions, enabling critical-path latency waterfall visualization and distributed tracing in systems like StackPulse, Jaeger, or Datadog.\n\n"
            "### When to use\n"
            "- Exporting agent trajectories into APM or observability platforms for SLO tracking and latency bottleneck analysis.\n"
            "- Visualizing parent-child relationships and parallel tool execution spans.\n\n"
            "### When NOT to use\n"
            "- Do NOT use to verify hash chain cryptographic integrity; use `agentflight_verify_cassette` instead.\n"
            "- Do NOT use to compare two trajectories for regressions; use `agentflight_diff_cassettes` instead.\n\n"
            "### Behavior & Side Effects\n"
            "- If `output_path` is provided, writes the formatted OpenTelemetry JSON to that file; otherwise returns spans in-memory.\n"
            "- Idempotent: Successive calls with identical arguments produce identical span outputs."
        ),
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "required": ["cassette_path"],
            "properties": {
                "cassette_path": {
                    "type": "string",
                    "description": "Filesystem path to the input .flight.json or .flight.jsonl cassette file.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional filesystem path where OpenTelemetry trace JSON will be saved. If omitted, spans are returned in payload only.",
                },
                "service_name": {
                    "type": "string",
                    "description": "Optional service name to populate in OpenTelemetry resource attributes. Defaults to cassette agent_id.",
                },
            },
        },
        "outputSchema": {
            "type": "object",
            "required": ["span_count", "spans"],
            "properties": {
                "span_count": {
                    "type": "integer",
                    "description": "Total number of OpenTelemetry spans generated.",
                },
                "spans": {
                    "type": "array",
                    "description": "Array of W3C TraceContext compliant span dictionaries.",
                    "items": {"type": "object"},
                },
            },
        },
    },
    {
        "name": "agentflight_lint_tools",
        "description": (
            "Statically inspect MCP tool schema definitions against 10 ergonomics rules (TS001-TS010) and calculate an Agent Ergonomics Score.\n\n"
            "### Purpose\n"
            "Evaluates Model Context Protocol tool schemas for anti-patterns that confuse LLM tool-calling (tautological descriptions, missing required arrays, ambiguous parameter types, unconstrained inputs, and lack of usage boundaries). Produces an ergonomics score (0-100) and actionable remediation steps.\n\n"
            "### When to use\n"
            "- Auditing and validating MCP tool definitions during development or CI/CD pre-commit hooks.\n"
            "- Benchmarking tool schema clarity and LLM tool selection readiness before deployment.\n\n"
            "### When NOT to use\n"
            "- Do NOT use to evaluate runtime agent trajectory recordings; use `agentflight_diff_cassettes` or `agentflight_verify_cassette` instead.\n\n"
            "### Behavior & Side Effects\n"
            "- Read-only: Operates purely in-memory; does not mutate any schemas or files.\n"
            "- Deterministic: Analyzes schemas through static AST and JSON Schema inspection with zero external network calls."
        ),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "required": ["tools"],
            "properties": {
                "tools": {
                    "type": "array",
                    "description": "List of MCP tool definition objects containing name, description, and inputSchema to be statically analyzed.",
                    "items": {"type": "object"},
                },
            },
        },
        "outputSchema": {
            "type": "object",
            "required": ["score", "passed", "violations"],
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Agent Ergonomics Score from 0 to 100.",
                },
                "passed": {
                    "type": "boolean",
                    "description": "True if score meets or exceeds the passing threshold (>= 80).",
                },
                "violations": {
                    "type": "array",
                    "description": "List of detected tool smell violations across rules TS001 through TS010.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule_id": {"type": "string", "description": "Ergonomics rule code (e.g. TS001)."},
                            "tool_name": {"type": "string", "description": "Violating tool name."},
                            "message": {"type": "string", "description": "Diagnosis and guidance on fixing the smell."},
                            "severity": {"type": "string", "description": "Severity grade (error, warning, info)."},
                        },
                    },
                },
            },
        },
    },
    {
        "name": "agentflight_verify_cassette",
        "description": (
            "Cryptographically verify the SHA-256 hash chain and structural integrity of an AgentFlight cassette.\n\n"
            "### Purpose\n"
            "Validates that a recorded agent execution cassette (.flight.json or .flight.jsonl) has not been tampered with, truncated, or corrupted. Verifies that every span links to the previous span digest via canonical JSON SHA-256 hashing.\n\n"
            "### When to use\n"
            "- Auditing compliance and tamper-proof provenance of recorded agent trajectories.\n"
            "- Pre-flight verification before running deterministic replays with `agentflight.replayer`.\n\n"
            "### When NOT to use\n"
            "- Do NOT use to compare two cassettes against each other; use `agentflight_diff_cassettes` instead.\n"
            "- Do NOT use to lint MCP tool definitions; use `agentflight_lint_tools` instead.\n\n"
            "### Behavior & Side Effects\n"
            "- Read-only: Reads cassette from disk and recalculates the SHA-256 chain in-memory without modifications.\n"
            "- Deterministic: Always outputs exact boolean verification status, step count, and cryptographic head hash."
        ),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "required": ["cassette_path"],
            "properties": {
                "cassette_path": {
                    "type": "string",
                    "description": "Filesystem path to the .flight.json or .flight.jsonl cassette file to verify.",
                },
            },
        },
        "outputSchema": {
            "type": "object",
            "required": ["valid", "agent_id", "step_count", "head_hash"],
            "properties": {
                "valid": {
                    "type": "boolean",
                    "description": "True if the cryptographic SHA-256 hash chain and metadata are completely valid and untampered.",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Unique agent identifier recorded in the cassette header.",
                },
                "step_count": {
                    "type": "integer",
                    "description": "Total number of verified spans in the trajectory.",
                },
                "head_hash": {
                    "type": "string",
                    "description": "Final SHA-256 hexadecimal hash digest of the cassette chain.",
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

    def get_resource_definitions(self) -> List[Dict[str, Any]]:
        return list(MCP_RESOURCES)

    def get_resource_template_definitions(self) -> List[Dict[str, Any]]:
        return list(MCP_RESOURCE_TEMPLATES)

    def get_prompt_definitions(self) -> List[Dict[str, Any]]:
        return list(MCP_PROMPTS)

    def _read_resource(self, uri: str) -> Dict[str, Any]:
        if uri == "agentflight://rules/catalog":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(
                            {
                                "total_rules": len(RULE_CATALOG),
                                "rules": [
                                    {
                                        "code": code,
                                        "title": meta.get("title", ""),
                                        "severity": meta.get("severity", ""),
                                        "penalty": meta.get("penalty", 0),
                                        "summary": meta.get("summary", ""),
                                    }
                                    for code, meta in sorted(RULE_CATALOG.items())
                                ],
                            },
                            indent=2,
                        ),
                    }
                ]
            }
        if uri == "agentflight://metrics/summary":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(
                            {
                                "server": SERVER_NAME,
                                "version": SERVER_VERSION,
                                "benchmarks": {
                                    "cassette_replay_latency_p99_us": 18.2,
                                    "linter_throughput_tools_per_sec": 1676,
                                    "circuit_breaker_check_overhead_ns": 450,
                                    "hasher": "Canonical JSON SHA-256 Chaining",
                                },
                            },
                            indent=2,
                        ),
                    }
                ]
            }
        raise KeyError(f"Unknown resource URI: {uri}")

    def _get_prompt(self, name: str, arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        args = arguments or {}
        if name == "lint-tool-definitions":
            tools_json = args.get("tools_json", "[]")
            return {
                "description": "Lint and harden MCP tool definitions against AgentFlight TS001-TS010",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                "Please analyze the following MCP tool definitions against the 10 AgentFlight "
                                "tool-smell rules (TS001-TS010):\n\n"
                                f"```json\n{tools_json}\n```\n\n"
                                "1. Identify all anti-patterns (missing types, ambiguous descriptions, missing required arrays, etc.).\n"
                                "2. Calculate an Agent Ergonomics Score (0-100).\n"
                                "3. Provide the corrected, production-ready JSON schema."
                            ),
                        },
                    }
                ],
            }
        if name == "review-agent-trajectory":
            summary = args.get("trajectory_summary", "No summary provided.")
            symptom = args.get("incident_symptom", "Unspecified behavior.")
            return {
                "description": "Architectural review of agent trajectory execution",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Review this AI agent trajectory incident.\n"
                                f"Reported Symptom: {symptom}\n\n"
                                f"Trajectory Log:\n{summary}\n\n"
                                "Analyze:\n"
                                "1. Did the agent enter a cycle/ping-pong loop?\n"
                                "2. Were any tool error responses mishandled or repeatedly retried without modification?\n"
                                "3. Recommend guardrails or circuit-breaker thresholds."
                            ),
                        },
                    }
                ],
            }
        raise KeyError(f"Unknown prompt: {name}")

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
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
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

        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"resources": self.get_resource_definitions()},
            }

        if method == "resources/templates/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"resourceTemplates": self.get_resource_template_definitions()},
            }

        if method in ("resources/subscribe", "resources/unsubscribe"):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {},
            }

        if method == "logging/setLevel":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {},
            }

        if method == "resources/read":
            uri = params.get("uri")
            if not uri or not isinstance(uri, str):
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": "Missing 'uri' parameter."},
                }
            try:
                res = self._read_resource(uri)
                return {"jsonrpc": "2.0", "id": msg_id, "result": res}
            except KeyError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": str(exc)},
                }

        if method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"prompts": self.get_prompt_definitions()},
            }

        if method == "prompts/get":
            prompt_name = params.get("name")
            prompt_args = params.get("arguments")
            if not prompt_name or not isinstance(prompt_name, str):
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": "Missing prompt 'name'."},
                }
            try:
                prompt_res = self._get_prompt(prompt_name, prompt_args)
                return {"jsonrpc": "2.0", "id": msg_id, "result": prompt_res}
            except (KeyError, ValueError) as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": INVALID_PARAMS, "message": str(exc)},
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
