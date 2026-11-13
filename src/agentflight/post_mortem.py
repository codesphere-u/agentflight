"""
agentflight.post_mortem
=======================
Automated Flight Data Recorder (FDR) Crash & Incident Investigator for AI Agents.

Analyzes recorded agent flight cassettes to reconstruct root causes,
timeline cascades, cost runaway, loop oscillations, and blast radius.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from .recorder import verify_cassette

IncidentSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "CLEAN"]
RootCauseCategory = Literal[
    "OSCILLATION_TRAP",
    "UNHANDLED_TOOL_FAULT",
    "BUDGET_EXHAUSTION",
    "LATENCY_SPIKE",
    "DESTRUCTIVE_SIDE_EFFECT",
    "INTEGRITY_TAMPER",
    "HEALTHY_FLIGHT",
]

MUTATION_KEYWORDS = {
    "delete", "remove", "drop", "write", "update", "patch", "modify",
    "charge", "pay", "send", "post", "execute", "exec", "kill", "deploy"
}


@dataclass
class TelemetryEvent:
    step_index: int
    actor: str
    kind: str
    latency_ms: float
    cost_usd: float
    tokens: int
    status: str
    is_mutation: bool
    is_anomaly: bool
    anomaly_reason: Optional[str] = None


@dataclass
class IncidentReport:
    flight_id: str
    agent_id: str
    cassette_version: str
    severity: IncidentSeverity
    root_cause: RootCauseCategory
    summary: str
    fault_inception_step: Optional[int]
    total_steps: int
    total_cost_usd: float
    total_tokens: int
    total_latency_ms: float
    is_hash_chain_valid: bool
    blast_radius_mutations: List[Dict[str, Any]]
    recommendations: List[str]
    timeline: List[TelemetryEvent]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        """Render AAIB / NTSB-grade Aircraft Incident Report in Markdown."""
        sev_badge = {
            "CRITICAL": "🔴 **CRITICAL INCIDENT**",
            "HIGH": "🟠 **HIGH SEVERITY**",
            "MEDIUM": "🟡 **MEDIUM SEVERITY**",
            "LOW": "🔵 **LOW SEVERITY**",
            "CLEAN": "🟢 **FLIGHT CLEAN (NO ANOMALIES)**",
        }.get(self.severity, self.severity)

        integrity_str = "✅ SHA-256 Cryptographically Verified" if self.is_hash_chain_valid else "❌ Cryptographic Chain Corrupted"
        fault_step_str = f"Step #{self.fault_inception_step}" if self.fault_inception_step is not None else "None"

        md = [
            f"# ✈️ Black-Box Incident Investigation Report: {self.flight_id}",
            "> Official Agent Flight Data Recorder (FDR) Analysis",
            "",
            "| Metric | Assessment |",
            "| :--- | :--- |",
            f"| **Incident Status** | {sev_badge} |",
            f"| **Root Cause** | `{self.root_cause}` |",
            f"| **Agent Identifier** | `{self.agent_id}` |",
            f"| **Fault Inception** | **{fault_step_str}** |",
            f"| **Total Steps** | `{self.total_steps}` |",
            f"| **Cumulative Cost** | `${self.total_cost_usd:.4f}` |",
            f"| **Cumulative Tokens** | `{self.total_tokens:,}` |",
            f"| **Airspeed Latency** | `{self.total_latency_ms:.1f} ms` |",
            f"| **Cassette Integrity** | {integrity_str} |",
            "",
            "## 📋 Executive Summary",
            f"{self.summary}",
            "",
        ]

        if self.blast_radius_mutations:
            md.extend([
                "## ⚠️ Blast Radius Assessment (Destructive Operations)",
                f"The agent executed **{len(self.blast_radius_mutations)}** potentially state-mutating operations prior to termination:",
                "",
                "| Step | Action | Status | Parameters |",
                "| :---: | :--- | :---: | :--- |",
            ])
            for m in self.blast_radius_mutations:
                args_str = json.dumps(m.get("input_payload", {}))
                if len(args_str) > 60:
                    args_str = args_str[:57] + "..."
                md.append(f"| {m.get('step_index')} | `{m.get('actor')}` | `{m.get('status')}` | `{args_str}` |")
            md.append("")

        md.extend([
            "## 🛠️ Corrective Safety Recommendations",
        ])
        for r in self.recommendations:
            md.append(f"- {r}")
        md.append("")

        md.extend([
            "## ⏱️ Flight Telemetry Timeline",
            "",
            "| Step | Actor | Kind | Latency | Cost | Status | Notes |",
            "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ])
        for ev in self.timeline:
            flag = f"🚨 {ev.anomaly_reason}" if ev.is_anomaly else ("⚡ Mutation" if ev.is_mutation else "—")
            stat_icon = "✅" if ev.status == "ok" else "❌"
            md.append(
                f"| {ev.step_index} | `{ev.actor}` | `{ev.kind}` | {ev.latency_ms:.1f}ms | ${ev.cost_usd:.4f} | {stat_icon} {ev.status} | {flag} |"
            )

        md.append("")
        md.append("---")
        md.append("*Generated automatically by AgentFlight FDR Engine • CodeSphere Innovations*")
        return "\n".join(md)


class FlightPostMortemAnalyzer:
    """Investigates recorded cassettes to pinpoint anomalies, loops, and runaway costs."""

    def __init__(
        self,
        *,
        max_single_step_latency_ms: float = 8000.0,
        max_cost_ceiling_usd: float = 2.00,
        oscillation_window: int = 4,
    ) -> None:
        self.max_single_step_latency_ms = max_single_step_latency_ms
        self.max_cost_ceiling_usd = max_cost_ceiling_usd
        self.oscillation_window = oscillation_window

    def analyze(self, cassette_data: Union[Dict[str, Any], str, Path]) -> IncidentReport:
        if isinstance(cassette_data, (str, Path)):
            with open(cassette_data, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = cassette_data

        agent_id = str(data.get("agent_id", "unknown-agent"))
        flight_id = str(data.get("metadata", {}).get("flight_id", f"FLIGHT-{agent_id[:8].upper()}"))
        version = str(data.get("version", "1.0.0"))
        spans_raw = data.get("spans", [])

        # 1. Cryptographic chain check
        is_chain_valid = False
        try:
            is_chain_valid = verify_cassette(data)
        except Exception:
            is_chain_valid = False

        total_steps = len(spans_raw)
        total_cost = float(data.get("total_cost_usd", sum(s.get("cost_usd", 0.0) for s in spans_raw)))
        total_tokens = int(data.get("total_tokens", sum(s.get("prompt_tokens", 0) + s.get("completion_tokens", 0) for s in spans_raw)))
        total_latency = float(data.get("total_latency_ms", sum(s.get("latency_ms", 0.0) for s in spans_raw)))

        timeline: List[TelemetryEvent] = []
        mutations: List[Dict[str, Any]] = []

        root_cause: RootCauseCategory = "HEALTHY_FLIGHT"
        severity: IncidentSeverity = "CLEAN"
        fault_step: Optional[int] = None
        summary = "Trajectory executed cleanly with no fatal loop anomalies, cost runaway, or unhandled faults."
        recommendations: List[str] = [
            "Maintain current tool schema ergonomics and guard constraints.",
            "Record golden baseline cassettes for continuous CI regression testing.",
        ]

        # 2. Sequential analysis across recorded spans
        recent_actors: List[str] = []

        for i, span in enumerate(spans_raw):
            actor = str(span.get("actor", "unknown"))
            kind = str(span.get("kind", "tool_call"))
            lat = float(span.get("latency_ms", 0.0))
            cost = float(span.get("cost_usd", 0.0))
            tokens = int(span.get("prompt_tokens", 0)) + int(span.get("completion_tokens", 0))
            status = str(span.get("status", "ok"))

            # Check if actor implies state mutation
            is_mut = any(kw in actor.lower() for kw in MUTATION_KEYWORDS)
            if is_mut:
                mutations.append(span)

            is_anomaly = False
            anomaly_reason = None

            # Check for error status
            if status != "ok":
                is_anomaly = True
                anomaly_reason = f"Tool returned failure: {status}"
                if fault_step is None:
                    fault_step = i
                    root_cause = "UNHANDLED_TOOL_FAULT"
                    severity = "HIGH"

            # Check for latency spike
            elif lat > self.max_single_step_latency_ms:
                is_anomaly = True
                anomaly_reason = f"Latency spike: {lat:.0f}ms > {self.max_single_step_latency_ms:.0f}ms"
                if fault_step is None and severity in ("CLEAN", "LOW"):
                    fault_step = i
                    root_cause = "LATENCY_SPIKE"
                    severity = "MEDIUM"

            # Loop oscillation detection
            recent_actors.append(actor)
            if len(recent_actors) >= 4:
                window = recent_actors[-4:]
                if window[0] == window[2] and window[1] == window[3] and window[0] != window[1]:
                    is_anomaly = True
                    anomaly_reason = f"2-cycle oscillation between {window[0]} and {window[1]}"
                    if root_cause != "OSCILLATION_TRAP":
                        fault_step = i - 3
                        root_cause = "OSCILLATION_TRAP"
                        severity = "CRITICAL"

            timeline.append(
                TelemetryEvent(
                    step_index=i,
                    actor=actor,
                    kind=kind,
                    latency_ms=lat,
                    cost_usd=cost,
                    tokens=tokens,
                    status=status,
                    is_mutation=is_mut,
                    is_anomaly=is_anomaly,
                    anomaly_reason=anomaly_reason,
                )
            )

        # Budget runaway check
        if total_cost > self.max_cost_ceiling_usd:
            root_cause = "BUDGET_EXHAUSTION"
            severity = "CRITICAL"
            fault_step = next((t.step_index for t in timeline if t.cost_usd > 0.5), 0)

        # Integrity failure check
        if not is_chain_valid:
            severity = "CRITICAL"
            root_cause = "INTEGRITY_TAMPER"
            summary = "Cassette cryptographic SHA-256 hash chain verification FAILED. Spans may have been manipulated or corrupted post-recording."
            recommendations.insert(0, "Investigate storage medium or pipeline tampering. Re-record clean trajectory.")

        # Construct contextual summaries and recommendations
        if root_cause == "OSCILLATION_TRAP":
            summary = (
                f"Agent entered a recursive tool-calling oscillation trap starting at step #{fault_step}. "
                f"The model repeatedly ping-ponged between tools without making progress toward resolution."
            )
            recommendations = [
                "Configure `TrajectoryCircuitBreaker(max_oscillations=2)` to sever runaway loops automatically.",
                "Review tool response schemas to ensure tools return definitive terminal guidance when queries yield empty results.",
                "Inject anti-loop prompt directives in the agent system instruction.",
            ]
        elif root_cause == "UNHANDLED_TOOL_FAULT":
            summary = (
                f"A downstream tool failure occurred at step #{fault_step}. "
                f"The agent did not safely handle the structured error payload and cascaded into secondary failures."
            )
            recommendations = [
                "Add defensive schema verification and error boundary handlers around downstream tool callers.",
                "Ensure tool error messages return actionable self-correction context (`isError: true`).",
            ]
        elif root_cause == "BUDGET_EXHAUSTION":
            summary = (
                f"Flight exceeded maximum allowable financial budget ceiling of ${self.max_cost_ceiling_usd:.2f} "
                f"(Actual spend: ${total_cost:.4f} across {total_tokens:,} tokens)."
            )
            recommendations = [
                "Activate `agentflight` pre-execution cost circuit breaking before initiating multi-turn runs.",
                "Compress prompt context and truncate heavy tool schemas via `agentflight.linter`.",
            ]

        return IncidentReport(
            flight_id=flight_id,
            agent_id=agent_id,
            cassette_version=version,
            severity=severity,
            root_cause=root_cause,
            summary=summary,
            fault_inception_step=fault_step,
            total_steps=total_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            total_latency_ms=total_latency,
            is_hash_chain_valid=is_chain_valid,
            blast_radius_mutations=mutations,
            recommendations=recommendations,
            timeline=timeline,
        )
