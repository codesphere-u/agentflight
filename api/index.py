"""Vercel Serverless entrypoint for AgentFlight.

Exposes the MCP server over **Streamable HTTP** (``POST /mcp``) plus a
``/health`` probe. The gateway is stateless and hardened for public hosting:

* strict JSON-RPC 2.0 envelopes (parse / invalid-request / internal errors),
* request body size limit,
* tools that touch the server filesystem or run commands are NOT exposed on
  the hosted deployment (use the local stdio install for those).
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
for _p in (str(SRC_DIR), str(ROOT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from agentflight._version import __version__
from agentflight.mcp_server import AgentFlightMCPServer
from agentflight.telemetry import ServerMetrics, emit_structured_log, resolve_request_id

try:
    from portal import render_developer_portal
except ImportError:
    from api.portal import render_developer_portal

SERVER_NAME = "agentflight"
SERVER_VERSION = __version__
MAX_BODY_BYTES = max(1, int(os.environ.get("MCP_MAX_BODY_BYTES", "1000000")))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("MCP_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
] or ["*"]

# Best-effort per-IP sliding-window rate limit. State is per serverless instance, so it
# bounds abuse of a warm instance but is not a global quota (use Vercel Firewall for that).
RATE_LIMIT_PER_MIN = int(os.environ.get("MCP_RATE_LIMIT_PER_MIN", "60"))
_hits: Dict[str, deque] = defaultdict(deque)
metrics = ServerMetrics(service_name=SERVER_NAME, version=SERVER_VERSION, runtime="vercel-serverless")


def _check_upstash_rate_limit(ip: str, limit: int) -> Tuple[bool, Optional[int]]:
    """
    Optional zero-dep Upstash Redis REST distributed rate limiter.
    Returns `(handled, retry_after_seconds)` and fails open to local memory on error.
    """
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url or not token:
        return False, None

    parsed = urllib.parse.urlparse(url)
    is_local_http = parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme != "https" and not is_local_http:
        return False, None

    bucket = int(time.time() // 60)
    key = f"agentflight:rl:{ip}:{bucket}"
    payload = json.dumps([["INCR", key], ["EXPIRE", key, "120"]]).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/pipeline",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            count = int(data[0]["result"])
            if count > limit:
                return True, max(1, 60 - int(time.time() % 60))
            return True, None
    except Exception:
        return False, None
    return False, None


def _rate_limited(request: Request) -> Optional[int]:
    """Return Retry-After seconds when the caller exceeded the limit, else None."""
    if RATE_LIMIT_PER_MIN <= 0:
        return None
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")

    handled, retry_after = _check_upstash_rate_limit(ip, RATE_LIMIT_PER_MIN)
    if handled:
        return retry_after

    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        return max(1, int(60 - (now - q[0])))
    q.append(now)
    if len(_hits) > 10_000:  # bound memory
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            _hits.pop(k, None)
    return None

# Tools hidden and refused on the public hosted deployment (filesystem / process access).
HOSTED_BLOCKED_TOOLS = frozenset(['agentflight_diff_cassettes', 'agentflight_export_otel', 'agentflight_verify_cassette'])
# Per-tool arguments that are refused (and stripped from the advertised schema) when hosted.
HOSTED_FORBIDDEN_ARGS: Dict[str, List[str]] = {}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
INTERNAL_ERROR = -32603

mcp_engine = AgentFlightMCPServer()

app = FastAPI(
    title=f"AgentFlight MCP Server ({SERVER_VERSION})",
    description="High-performance Agent Tool Ergonomics & Flight Recorder Model Context Protocol (MCP) server running on Vercel Serverless. "
                "Supports static tool-smell linting, token-budget compiling, trajectory telemetry, and official OpenAny integration. "
                "Created and owned by Akandwanaho Ivan Alvin. Independently owned open-source AI infrastructure.",
    version=SERVER_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Akandwanaho Ivan Alvin (Creator & Owner)",
        "url": "https://github.com/codesphere-u/agentflight",
        "email": "codesphereinnovationz@gmail.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id", "X-Request-ID"],
)


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next: Any) -> Response:
    req_id = resolve_request_id(request.headers.get("x-request-id"))
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000.0
    metrics.inc_request(response.status_code)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers["X-Request-ID"] = req_id
    if os.environ.get("AGENTFLIGHT_LOG_JSON") == "1":
        emit_structured_log(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=elapsed_ms,
        )
    return response


def _error(code: int, message: str, req_id: Any = None, status: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}},
    )


def _sanitize_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    visible = []
    for tool in tools:
        name = tool.get("name")
        if name in HOSTED_BLOCKED_TOOLS:
            continue
        tool = copy.deepcopy(tool)
        schema = tool.get("inputSchema") or {}
        if isinstance(name, str):
            for arg in HOSTED_FORBIDDEN_ARGS.get(name, []):
                schema.get("properties", {}).pop(arg, None)
                if arg in schema.get("required", []):
                    schema["required"].remove(arg)
        visible.append(tool)
    return visible


def _dispatch(message: Any) -> Optional[Dict[str, Any]]:
    """Process one JSON-RPC message. Returns None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id") if isinstance(message, dict) else None,
            "error": {"code": INVALID_REQUEST, "message": "Invalid JSON-RPC 2.0 request."},
        }

    method = message["method"]
    req_id = message.get("id")
    is_notification = "id" not in message

    if method == "ping":
        return None if is_notification else {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/call":
        raw_params = message.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        name = params.get("name")
        args = params.get("arguments") or {}
        refused = None
        if isinstance(name, str) and name in HOSTED_BLOCKED_TOOLS:
            refused = f"Tool '{name}' is disabled on the hosted deployment (filesystem/process access). Install locally via stdio to use it."
        elif isinstance(name, str):
            for arg in HOSTED_FORBIDDEN_ARGS.get(name, []):
                if isinstance(args, dict) and arg in args:
                    refused = f"Argument '{arg}' is disabled on the hosted deployment. Pass the content inline instead."
                    break
        if refused:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": refused}], "isError": True},
            }

    try:
        response = mcp_engine.handle_request(message)
    except Exception:  # noqa: BLE001 - never leak internals to public callers
        metrics.inc_mcp(method, is_error=True)
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": INTERNAL_ERROR, "message": "Internal server error."}}

    if response is None or is_notification:
        metrics.inc_mcp(method, is_error=False)
        return None

    is_err = bool(response.get("error")) or bool(
        isinstance(response.get("result"), dict) and response["result"].get("isError")
    )
    metrics.inc_mcp(method, is_error=is_err)

    if method == "tools/list" and isinstance(response.get("result"), dict):
        response["result"]["tools"] = _sanitize_tools(response["result"].get("tools", []))
    return cast(Optional[Dict[str, Any]], response)


@app.get("/")
@app.get("/health")
@app.get("/healthz")
@app.get("/api/health")
async def health_check(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        tools_resp = mcp_engine.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) or {}
        resources_resp = mcp_engine.handle_request({"jsonrpc": "2.0", "id": 2, "method": "resources/list"}) or {}
        prompts_resp = mcp_engine.handle_request({"jsonrpc": "2.0", "id": 3, "method": "prompts/list"}) or {}
        tools = _sanitize_tools(tools_resp.get("result", {}).get("tools", []))
        resources = resources_resp.get("result", {}).get("resources", [])
        prompts = prompts_resp.get("result", {}).get("prompts", [])
        html_content = render_developer_portal(
            server_name=SERVER_NAME,
            server_version=SERVER_VERSION,
            tagline="AI Agent Black-Box Flight Recorder & MCP Tool-Smell Linter",
            endpoint_url=f"{str(request.base_url).rstrip('/')}/mcp",
            github_url="https://github.com/codesphere-u/agentflight",
            tools=tools,
            resources=resources,
            prompts=prompts,
            sample_tool_call={"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "agentflight_lint_tools", "arguments": {"tools_json": "[{\"name\": \"exec\", \"description\": \"run cmd\"}]"}}},
        )
        return HTMLResponse(content=html_content)

    return {
        "status": "healthy",
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "protocol": "mcp-jsonrpc-2.0",
        "transport": ["streamable-http", "sse"],
        "endpoint": "/mcp",
        "runtime": "vercel-serverless",
        "hosted_restrictions": sorted(HOSTED_BLOCKED_TOOLS),
    }


@app.head("/")
@app.head("/health")
@app.head("/healthz")
@app.head("/api/health")
@app.head("/metrics")
async def health_head() -> Response:
    return Response(status_code=200, media_type="application/json")


@app.get("/metrics")
@app.get("/api/metrics")
async def server_metrics(request: Request) -> Response:
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse(content=metrics.snapshot())
    return Response(
        content=metrics.to_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/mcp")
async def mcp_get(request: Request):
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return await sse_legacy(request)
    if "text/html" in accept:
        return await health_check(request)
    return Response(status_code=405, headers={"Allow": "POST, OPTIONS"})


@app.get("/sse")
async def sse_legacy(request: Request):
    """Legacy discovery stream. Responses are returned inline on POST /mcp (Streamable HTTP)."""
    session_id = str(uuid.uuid4())

    async def event_generator():
        yield f"event: endpoint\ndata: /messages?session_id={session_id}\n\n"
        yield f"event: ping\ndata: {json.dumps({'sessionId': session_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.post("/mcp")
@app.post("/messages")
@app.post("/")
async def handle_jsonrpc(request: Request):
    retry = _rate_limited(request)
    if retry is not None:
        metrics.inc_rate_limited()
        resp = _error(-32000, "Rate limit exceeded. Slow down or self-host.", status=429)
        resp.headers["Retry-After"] = str(retry)
        return resp
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return _error(INVALID_REQUEST, "Request body too large.", status=413)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return _error(PARSE_ERROR, "Parse error.", status=400)

    if isinstance(body, list):
        if not body:
            return _error(INVALID_REQUEST, "Empty batch.", status=400)
        responses = [r for r in (_dispatch(m) for m in body) if r is not None]
        if not responses:
            return Response(status_code=202)
        return JSONResponse(content=responses)

    result = _dispatch(body)
    if result is None:
        return Response(status_code=202)
    return JSONResponse(content=result)
