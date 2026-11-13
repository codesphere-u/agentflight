"""
Lightweight Zero-Dependency Server Telemetry & Request Correlation.

Provides thread-safe Prometheus/JSON counters (`ServerMetrics`), validated
`X-Request-ID` propagation (`resolve_request_id`), and opt-in structured JSON
telemetry logs shared across both standalone HTTP and Vercel ASGI servers.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
import uuid
from typing import Any, Dict, Optional

_SAFE_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


def resolve_request_id(raw_value: Optional[str]) -> str:
    """Validate an inbound X-Request-ID header or mint a compact correlation ID."""
    if raw_value:
        cleaned = raw_value.strip()
        if _SAFE_REQUEST_ID_RE.match(cleaned):
            return cleaned
    return uuid.uuid4().hex[:16]


class ServerMetrics:
    """Thread-safe in-memory server telemetry with Prometheus text exposition."""

    def __init__(
        self,
        service_name: str = "agentflight",
        version: str = "0.0.0",
        runtime: str = "http",
    ) -> None:
        self.service_name = service_name
        self.version = version
        self.runtime = runtime
        self.started_at = time.time()
        self._lock = threading.Lock()
        self.requests_total = 0
        self.requests_4xx = 0
        self.requests_5xx = 0
        self.mcp_calls_total = 0
        self.mcp_tool_calls_total = 0
        self.mcp_errors_total = 0
        self.rate_limited_total = 0

    def inc_request(self, status_code: int) -> None:
        with self._lock:
            self.requests_total += 1
            if 400 <= status_code < 500:
                self.requests_4xx += 1
            elif status_code >= 500:
                self.requests_5xx += 1

    def inc_mcp(self, method: str, *, is_error: bool = False) -> None:
        with self._lock:
            self.mcp_calls_total += 1
            if method == "tools/call":
                self.mcp_tool_calls_total += 1
            if is_error:
                self.mcp_errors_total += 1

    def inc_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited_total += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "service": self.service_name,
                "version": self.version,
                "runtime": self.runtime,
                "uptime_seconds": round(max(0.0, time.time() - self.started_at), 3),
                "requests_total": self.requests_total,
                "requests_4xx": self.requests_4xx,
                "requests_5xx": self.requests_5xx,
                "mcp_calls_total": self.mcp_calls_total,
                "mcp_tool_calls_total": self.mcp_tool_calls_total,
                "mcp_errors_total": self.mcp_errors_total,
                "rate_limited_total": self.rate_limited_total,
            }

    def to_prometheus(self) -> str:
        snap = self.snapshot()
        labels = f'service="{self.service_name}",version="{self.version}",runtime="{self.runtime}"'
        lines = [
            "# HELP agentflight_info Static server metadata.",
            "# TYPE agentflight_info gauge",
            f"agentflight_info{{{labels}}} 1",
            "# HELP agentflight_uptime_seconds Server process uptime in seconds.",
            "# TYPE agentflight_uptime_seconds gauge",
            f'agentflight_uptime_seconds{{service="{self.service_name}"}} {snap["uptime_seconds"]}',
            "# HELP agentflight_requests_total Total HTTP requests handled.",
            "# TYPE agentflight_requests_total counter",
            f'agentflight_requests_total{{service="{self.service_name}"}} {snap["requests_total"]}',
            "# HELP agentflight_requests_4xx_total Total HTTP 4xx responses.",
            "# TYPE agentflight_requests_4xx_total counter",
            f'agentflight_requests_4xx_total{{service="{self.service_name}"}} {snap["requests_4xx"]}',
            "# HELP agentflight_requests_5xx_total Total HTTP 5xx responses.",
            "# TYPE agentflight_requests_5xx_total counter",
            f'agentflight_requests_5xx_total{{service="{self.service_name}"}} {snap["requests_5xx"]}',
            "# HELP agentflight_mcp_calls_total Total JSON-RPC MCP requests processed.",
            "# TYPE agentflight_mcp_calls_total counter",
            f'agentflight_mcp_calls_total{{service="{self.service_name}"}} {snap["mcp_calls_total"]}',
            "# HELP agentflight_mcp_tool_calls_total Total MCP tools/call invocations.",
            "# TYPE agentflight_mcp_tool_calls_total counter",
            f'agentflight_mcp_tool_calls_total{{service="{self.service_name}"}} {snap["mcp_tool_calls_total"]}',
            "# HELP agentflight_mcp_errors_total Total failed MCP responses or tool errors.",
            "# TYPE agentflight_mcp_errors_total counter",
            f'agentflight_mcp_errors_total{{service="{self.service_name}"}} {snap["mcp_errors_total"]}',
            "# HELP agentflight_rate_limited_total Total HTTP 429 rate-limited responses.",
            "# TYPE agentflight_rate_limited_total counter",
            f'agentflight_rate_limited_total{{service="{self.service_name}"}} {snap["rate_limited_total"]}',
        ]
        return "\n".join(lines) + "\n"


def emit_structured_log(
    *,
    request_id: str,
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a single-line JSON log record to stderr (never includes credentials/bodies)."""
    record: Dict[str, Any] = {
        "ts": round(time.time(), 3),
        "level": "error" if status >= 500 else ("warn" if status >= 400 else "info"),
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": round(latency_ms, 2),
    }
    if extra:
        record.update(extra)
    sys.stderr.write(json.dumps(record, separators=(",", ":")) + "\n")
