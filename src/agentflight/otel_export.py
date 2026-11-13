"""
agentflight.otel_export
=======================
OpenTelemetry / W3C TraceContext Span Exporter (`export_cassette_to_otel`).

Converts recorded `AgentFlight` cassette spans into W3C TraceContext / OpenTelemetry
compatible JSON spans (`trace_id`, `span_id`, `parent_span_id`, `service_name`,
`operation_name`, `operation`, `start_time_ms`, `duration_ms`, `status_code`,
`span_kind`, `attributes`) that can be ingested directly by `codesphere-u/stackpulse`
for critical-path DAG analysis and multi-window SLO burn-rate monitoring.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Union

from .recorder import FlightRecorder, TrajectorySpan

OTelStatusCode = Literal["OK", "ERROR", "UNSET"]
OTelSpanKind = Literal["SERVER", "CLIENT", "INTERNAL", "PRODUCER", "CONSUMER"]

DEFAULT_BASE_START_TIME_MS = 1767225600000.0  # 2026-01-01T00:00:00Z in epoch ms


def _derive_w3c_trace_id(head_hash: str, agent_id: str) -> str:
    """Derive a deterministic 32-hex-char (128-bit) W3C trace_id from cassette hashes."""
    if head_hash and len(head_hash) >= 32 and head_hash != "0" * 64:
        return head_hash[:32].lower()
    digest = hashlib.sha256(f"agentflight:trace:{agent_id}".encode("utf-8")).hexdigest()
    return digest[:32]


def _derive_w3c_span_id(step_hash: str, trace_id: str, step_index: int) -> str:
    """Derive a deterministic 16-hex-char (64-bit) W3C span_id from a span's step_hash."""
    if step_hash and len(step_hash) >= 16:
        return step_hash[:16].lower()
    digest = hashlib.sha256(f"{trace_id}:span:{step_index}".encode("utf-8")).hexdigest()
    return digest[:16]


def _map_span_kind(kind: str) -> OTelSpanKind:
    if kind in ("tool_call", "mcp_rpc"):
        return "CLIENT"
    if kind == "llm_turn":
        return "INTERNAL"
    return "INTERNAL"


def _map_status_code(status: str) -> OTelStatusCode:
    if status == "error":
        return "ERROR"
    if status == "ok":
        return "OK"
    return "UNSET"


@dataclass(frozen=True)
class OTelSpanPayload:
    """W3C TraceContext / OpenTelemetry compatible span record."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    start_time_ms: float
    duration_ms: float
    status_code: OTelStatusCode
    span_kind: OTelSpanKind = "INTERNAL"
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def operation(self) -> str:
        """Alias matching `stackpulse.ingest.models.SpanRecord.operation`."""
        return self.operation_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "operation": self.operation_name,
            "start_time_ms": round(self.start_time_ms, 4),
            "duration_ms": round(self.duration_ms, 4),
            "status_code": self.status_code,
            "span_kind": self.span_kind,
            "attributes": dict(self.attributes),
        }


def export_cassette_to_otel(
    cassette: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
    *,
    service_name: Optional[str] = None,
    base_start_time_ms: float = DEFAULT_BASE_START_TIME_MS,
    include_root_span: bool = True,
    output_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Convert an `AgentFlight` cassette into a list of W3C TraceContext / OpenTelemetry
    span dictionaries ready for ingestion by `codesphere-u/stackpulse`.

    When `include_root_span=True` (default), synthesizes a root trace span
    (`parent_span_id=None`) representing the end-to-end agent trajectory, and links
    each recorded `TrajectorySpan` as a child span under that root span (with LLM turns
    acting as parent spans for immediately subsequent tool/MCP calls).
    """
    if isinstance(cassette, (str, Path)):
        rec = FlightRecorder.load(cassette, verify=True)
        spans = rec.spans
        agent_id = rec.agent_id
        head_hash = rec.head_hash
        metadata = rec.metadata
    elif isinstance(cassette, FlightRecorder):
        spans = cassette.spans
        agent_id = cassette.agent_id
        head_hash = cassette.head_hash
        metadata = cassette.metadata
    else:
        spans = list(cassette)
        agent_id = "agentflight-agent"
        head_hash = spans[-1].step_hash if spans else ""
        metadata = {}

    svc_name = service_name or agent_id or "agentflight-agent"
    trace_id = _derive_w3c_trace_id(head_hash, svc_name)
    root_span_id = hashlib.sha256(f"{trace_id}:root".encode("utf-8")).hexdigest()[:16]

    exported: List[OTelSpanPayload] = []
    cursor_ms = float(base_start_time_ms)
    current_llm_span_id: Optional[str] = root_span_id if include_root_span else None

    total_duration = round(sum(max(0.0, s.latency_ms) for s in spans), 4)
    total_tokens = sum(s.prompt_tokens + s.completion_tokens for s in spans)
    total_cost = round(sum(s.cost_usd for s in spans), 8)
    has_any_error = any(s.status == "error" for s in spans)

    if include_root_span:
        root_span = OTelSpanPayload(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            service_name=svc_name,
            operation_name=f"agent.trajectory.{svc_name}",
            start_time_ms=base_start_time_ms,
            duration_ms=total_duration,
            status_code="ERROR" if has_any_error else "OK",
            span_kind="SERVER",
            attributes={
                "agentflight.agent_id": agent_id,
                "agentflight.head_hash": head_hash,
                "agentflight.step_count": len(spans),
                "gen_ai.usage.total_tokens": total_tokens,
                "gen_ai.usage.cost_usd": total_cost,
                **{f"agentflight.meta.{k}": v for k, v in metadata.items()},
            },
        )
        exported.append(root_span)

    for sp in spans:
        sp_id = _derive_w3c_span_id(sp.step_hash, trace_id, sp.step_index)
        if sp.kind == "llm_turn":
            parent_id = root_span_id if include_root_span else None
            current_llm_span_id = sp_id
            span_svc = svc_name
        elif sp.kind in ("tool_call", "mcp_rpc"):
            parent_id = current_llm_span_id
            span_svc = sp.actor.split(".")[0] if "." in sp.actor else svc_name
        else:
            parent_id = root_span_id if include_root_span else None
            span_svc = svc_name

        dur = max(0.0, float(sp.latency_ms))
        attrs: Dict[str, Any] = {
            "agentflight.step_index": sp.step_index,
            "agentflight.kind": sp.kind,
            "agentflight.actor": sp.actor,
            "agentflight.step_hash": sp.step_hash,
            "agentflight.prev_hash": sp.prev_hash,
            "agentflight.input_hash": sp.input_hash,
            "gen_ai.usage.input_tokens": sp.prompt_tokens,
            "gen_ai.usage.output_tokens": sp.completion_tokens,
            "gen_ai.usage.total_tokens": sp.prompt_tokens + sp.completion_tokens,
            "gen_ai.usage.cost_usd": sp.cost_usd,
        }
        if sp.status == "error" and "error" in sp.output_payload:
            attrs["exception.message"] = str(sp.output_payload.get("error", ""))
            attrs["exception.type"] = str(sp.output_payload.get("error_type", "ToolError"))

        otel_span = OTelSpanPayload(
            trace_id=trace_id,
            span_id=sp_id,
            parent_span_id=parent_id,
            service_name=span_svc,
            operation_name=f"{sp.kind}:{sp.actor}",
            start_time_ms=cursor_ms,
            duration_ms=dur,
            status_code=_map_status_code(sp.status),
            span_kind=_map_span_kind(sp.kind),
            attributes=attrs,
        )
        exported.append(otel_span)
        cursor_ms += dur

    result_dicts = [item.to_dict() for item in exported]
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result_dicts, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return result_dicts
