"""
agentflight.diff
================
Trajectory Differential Analyzer & Regression Detector (`compare_cassettes`).

Compares a baseline cassette (`.flight.json` / `.flight.jsonl` / `FlightRecorder`)
against a candidate cassette across model or prompt upgrades to detect behavioral
regressions:
- Tool sequence divergence (Levenshtein / LCS edit distance on tool call sequences)
- New tool errors or loop/oscillation regressions
- Token & USD cost delta (`cost_delta_pct`, `token_delta_pct`) and latency delta (`latency_delta_pct`)
- Structural output drift
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .guard import CircuitBreakerTripped, TrajectoryCircuitBreaker
from .recorder import FlightRecorder, TrajectorySpan, canonical_hash


def _load_spans(
    source: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path]
) -> Tuple[str, List[TrajectorySpan]]:
    """Extract `(agent_id, spans)` from a FlightRecorder, span list, or cassette file path."""
    if isinstance(source, (str, Path)):
        rec = FlightRecorder.load(source, verify=True)
        return rec.agent_id, rec.spans
    if isinstance(source, FlightRecorder):
        return source.agent_id, source.spans
    return "inline-trajectory", list(source)


def compute_levenshtein_distance(seq_a: Sequence[str], seq_b: Sequence[str]) -> int:
    """Compute exact Wagner-Fischer Levenshtein edit distance between two sequences."""
    n, m = len(seq_a), len(seq_b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    curr = [0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i
        a_item = seq_a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if a_item == seq_b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            )
        prev, curr = curr, prev
    return prev[m]


def compute_lcs_length(seq_a: Sequence[str], seq_b: Sequence[str]) -> int:
    """Compute the Longest Common Subsequence (LCS) length between two sequences."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return 0
    dp = [0] * (m + 1)
    for a_item in seq_a:
        prev_diag = 0
        for j in range(1, m + 1):
            temp = dp[j]
            if a_item == seq_b[j - 1]:
                dp[j] = prev_diag + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev_diag = temp
    return dp[m]


def _pct_delta(baseline: float, candidate: float) -> float:
    """Compute percentage change `((candidate - baseline) / baseline) * 100.0`."""
    if abs(baseline) < 1e-12:
        if abs(candidate) < 1e-12:
            return 0.0
        return 100.0 if candidate > 0 else -100.0
    return round(((candidate - baseline) / baseline) * 100.0, 2)


def _detect_loop_regression(spans: Sequence[TrajectorySpan]) -> Optional[str]:
    """Run `TrajectoryCircuitBreaker` over spans to detect exact call loops or ping-pong cycles."""
    breaker = TrajectoryCircuitBreaker(
        max_identical_repeats=3,
        max_ping_pong_cycles=2,
        max_consecutive_errors=3,
        max_total_tokens=None,
        max_cost_usd=None,
    )
    try:
        for sp in spans:
            breaker.observe_span(sp)
    except CircuitBreakerTripped as exc:
        return f"{exc.reason} at step {exc.step_index}: {exc}"
    return None


@dataclass(frozen=True)
class TrajectoryDiffReport:
    """Immutable differential regression report comparing baseline vs. candidate cassettes."""

    regression_detected: bool
    similarity_score: float
    added_tools: List[str]
    removed_tools: List[str]
    cost_delta_pct: float
    token_delta_pct: float
    latency_delta_pct: float = 0.0
    levenshtein_distance: int = 0
    lcs_length: int = 0
    new_tool_errors: List[str] = field(default_factory=list)
    loop_regression: Optional[str] = None
    structural_output_drift: bool = False
    drift_reasons: List[str] = field(default_factory=list)
    summary_markdown: str = ""
    # Backward-compatible fields for v1.0.0 TrajectoryEvaluator consumers
    golden_steps: int = 0
    candidate_steps: int = 0
    tool_precision: float = 1.0
    tool_recall: float = 1.0
    tool_f1: float = 1.0
    argument_exact_match_rate: float = 1.0
    step_efficiency_ratio: float = 1.0
    golden_tokens: int = 0
    candidate_tokens: int = 0
    token_delta: int = 0
    golden_cost_usd: float = 0.0
    candidate_cost_usd: float = 0.0
    cost_delta_usd: float = 0.0
    goal_completion_score: float = 1.0
    passed: bool = True
    step_diffs: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regression_detected": self.regression_detected,
            "similarity_score": self.similarity_score,
            "added_tools": list(self.added_tools),
            "removed_tools": list(self.removed_tools),
            "cost_delta_pct": self.cost_delta_pct,
            "token_delta_pct": self.token_delta_pct,
            "latency_delta_pct": self.latency_delta_pct,
            "levenshtein_distance": self.levenshtein_distance,
            "lcs_length": self.lcs_length,
            "new_tool_errors": list(self.new_tool_errors),
            "loop_regression": self.loop_regression,
            "structural_output_drift": self.structural_output_drift,
            "drift_reasons": list(self.drift_reasons),
            "summary_markdown": self.summary_markdown,
            "golden_steps": self.golden_steps,
            "candidate_steps": self.candidate_steps,
            "tool_precision": self.tool_precision,
            "tool_recall": self.tool_recall,
            "tool_f1": self.tool_f1,
            "argument_exact_match_rate": self.argument_exact_match_rate,
            "step_efficiency_ratio": self.step_efficiency_ratio,
            "golden_tokens": self.golden_tokens,
            "candidate_tokens": self.candidate_tokens,
            "token_delta": self.token_delta,
            "golden_cost_usd": self.golden_cost_usd,
            "candidate_cost_usd": self.candidate_cost_usd,
            "cost_delta_usd": self.cost_delta_usd,
            "goal_completion_score": self.goal_completion_score,
            "passed": self.passed,
            "step_diffs": [
                d.to_dict() if hasattr(d, "to_dict") else asdict(d) if hasattr(d, "__dataclass_fields__") else d
                for d in self.step_diffs
            ],
        }


class TrajectoryDifferentialAnalyzer:
    """
    Differential Analyzer & Behavioral Regression Detector for AgentFlight cassettes.
    """

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.80,
        max_cost_increase_pct: float = 50.0,
        max_token_increase_pct: float = 50.0,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_cost_increase_pct = max_cost_increase_pct
        self.max_token_increase_pct = max_token_increase_pct

    def compare(
        self,
        baseline: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
        candidate: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
    ) -> TrajectoryDiffReport:
        """
        Compare `baseline` cassette against `candidate` cassette and return an immutable
        `TrajectoryDiffReport`.
        """
        base_id, b_spans = _load_spans(baseline)
        cand_id, c_spans = _load_spans(candidate)

        b_tool_spans = [s for s in b_spans if s.kind in ("tool_call", "mcp_rpc")] or b_spans
        c_tool_spans = [s for s in c_spans if s.kind in ("tool_call", "mcp_rpc")] or c_spans

        b_seq = [s.actor for s in b_tool_spans]
        c_seq = [s.actor for s in c_tool_spans]

        lev_dist = compute_levenshtein_distance(b_seq, c_seq)
        lcs_len = compute_lcs_length(b_seq, c_seq)
        max_seq_len = max(len(b_seq), len(c_seq))

        if max_seq_len == 0:
            seq_similarity = 1.0
        else:
            lev_sim = 1.0 - (lev_dist / max_seq_len)
            lcs_sim = (2.0 * lcs_len) / (len(b_seq) + len(c_seq)) if (len(b_seq) + len(c_seq)) > 0 else 1.0
            seq_similarity = round(0.5 * lev_sim + 0.5 * lcs_sim, 4)

        b_counts = Counter(b_seq)
        c_counts = Counter(c_seq)

        added_tools: List[str] = []
        removed_tools: List[str] = []
        for actor, cnt in sorted((c_counts - b_counts).items()):
            added_tools.extend([actor] * cnt)
        for actor, cnt in sorted((b_counts - c_counts).items()):
            removed_tools.extend([actor] * cnt)

        # Precision / Recall / F1
        matched_actors = sum((b_counts & c_counts).values())
        total_b_tools = sum(b_counts.values())
        total_c_tools = sum(c_counts.values())
        precision = matched_actors / total_c_tools if total_c_tools > 0 else (1.0 if total_b_tools == 0 else 0.0)
        recall = matched_actors / total_b_tools if total_b_tools > 0 else (1.0 if total_c_tools == 0 else 0.0)
        f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Argument exact signature match
        b_sigs = Counter((s.actor, canonical_hash(s.input_payload)) for s in b_tool_spans)
        c_sigs = Counter((s.actor, canonical_hash(s.input_payload)) for s in c_tool_spans)
        exact_sig_matches = sum((b_sigs & c_sigs).values())
        arg_exact_rate = exact_sig_matches / total_b_tools if total_b_tools > 0 else 1.0

        # Step efficiency
        if len(c_spans) == 0 and len(b_spans) == 0:
            efficiency = 1.0
        elif len(c_spans) == 0:
            efficiency = 0.0
        else:
            efficiency = min(1.0, len(b_spans) / len(c_spans))

        # Telemetry deltas
        b_tokens = sum(s.prompt_tokens + s.completion_tokens for s in b_spans)
        c_tokens = sum(s.prompt_tokens + s.completion_tokens for s in c_spans)
        b_cost = round(sum(s.cost_usd for s in b_spans), 8)
        c_cost = round(sum(s.cost_usd for s in c_spans), 8)
        b_latency = round(sum(s.latency_ms for s in b_spans), 4)
        c_latency = round(sum(s.latency_ms for s in c_spans), 4)

        token_delta_pct = _pct_delta(float(b_tokens), float(c_tokens))
        cost_delta_pct = _pct_delta(b_cost, c_cost)
        latency_delta_pct = _pct_delta(b_latency, c_latency)

        # Error regressions
        b_error_actors = Counter(s.actor for s in b_spans if s.status == "error")
        c_error_actors = Counter(s.actor for s in c_spans if s.status == "error")
        new_errors_counter = c_error_actors - b_error_actors
        new_tool_errors: List[str] = []
        for actor, cnt in sorted(new_errors_counter.items()):
            new_tool_errors.extend([actor] * cnt)

        # Loop / oscillation regression on candidate that wasn't in baseline
        base_loop = _detect_loop_regression(b_spans)
        cand_loop = _detect_loop_regression(c_spans)
        loop_regression = cand_loop if (cand_loop and cand_loop != base_loop) else None

        # Structural output drift on final step
        structural_output_drift = False
        if b_spans and c_spans:
            b_last = b_spans[-1]
            c_last = c_spans[-1]
            b_keys = set(b_last.output_payload.keys())
            c_keys = set(c_last.output_payload.keys())
            if b_last.status != c_last.status or b_keys != c_keys:
                structural_output_drift = True
            elif canonical_hash(b_last.output_payload) != canonical_hash(c_last.output_payload):
                # Check if types of values drifted or status changed
                for k in b_keys & c_keys:
                    if type(b_last.output_payload[k]) is not type(c_last.output_payload[k]):
                        structural_output_drift = True
                        break
        elif bool(b_spans) != bool(c_spans):
            structural_output_drift = True

        # Overall similarity score combining sequence similarity, argument match, and output structure
        output_agreement = 0.0 if structural_output_drift else 1.0
        similarity_score = round(
            0.50 * seq_similarity + 0.30 * arg_exact_rate + 0.20 * output_agreement,
            4,
        )

        drift_reasons: List[str] = []
        if lev_dist > 0:
            drift_reasons.append(
                f"Tool sequence edit distance={lev_dist} (LCS={lcs_len}, added={added_tools}, removed={removed_tools})"
            )
        if new_tool_errors:
            drift_reasons.append(f"New tool execution errors introduced: {new_tool_errors}")
        if loop_regression:
            drift_reasons.append(f"Loop/oscillation regression detected: {loop_regression}")
        if structural_output_drift:
            drift_reasons.append("Final trajectory step exhibited structural output schema/status drift")
        if cost_delta_pct > self.max_cost_increase_pct:
            drift_reasons.append(
                f"Cost increased by +{cost_delta_pct:.2f}% (exceeds +{self.max_cost_increase_pct:.1f}% threshold)"
            )
        if token_delta_pct > self.max_token_increase_pct:
            drift_reasons.append(
                f"Token usage increased by +{token_delta_pct:.2f}% (exceeds +{self.max_token_increase_pct:.1f}% threshold)"
            )
        if similarity_score < self.similarity_threshold:
            drift_reasons.append(
                f"Trajectory similarity score {similarity_score:.4f} fell below {self.similarity_threshold:.2f} threshold"
            )

        regression_detected = bool(
            new_tool_errors
            or loop_regression
            or structural_output_drift
            or cost_delta_pct > self.max_cost_increase_pct
            or token_delta_pct > self.max_token_increase_pct
            or similarity_score < self.similarity_threshold
        )

        status_badge = "REGRESSION DETECTED" if regression_detected else "NO REGRESSION (PASSED)"
        md_lines = [
            f"## AgentFlight Trajectory Differential Report (`{base_id}` -> `{cand_id}`)",
            f"- **Verdict**: **{status_badge}**",
            f"- **Similarity Score**: `{similarity_score:.4f}` (Levenshtein Distance: `{lev_dist}`, LCS: `{lcs_len}`)",
            f"- **Steps**: `{len(b_spans)}` baseline -> `{len(c_spans)}` candidate",
            f"- **Added Tools**: `{added_tools}` | **Removed Tools**: `{removed_tools}`",
            f"- **Token Delta**: `{b_tokens}` -> `{c_tokens}` (`{token_delta_pct:+.2f}%`)",
            f"- **Cost Delta**: `${b_cost:.6f}` -> `${c_cost:.6f}` (`{cost_delta_pct:+.2f}%`)",
            f"- **Latency Delta**: `{b_latency:.1f} ms` -> `{c_latency:.1f} ms` (`{latency_delta_pct:+.2f}%`)",
        ]
        if drift_reasons:
            md_lines.append("\n### Regression & Drift Findings")
            for reason in drift_reasons:
                md_lines.append(f"- {reason}")

        summary_markdown = "\n".join(md_lines)

        return TrajectoryDiffReport(
            regression_detected=regression_detected,
            similarity_score=similarity_score,
            added_tools=added_tools,
            removed_tools=removed_tools,
            cost_delta_pct=cost_delta_pct,
            token_delta_pct=token_delta_pct,
            latency_delta_pct=latency_delta_pct,
            levenshtein_distance=lev_dist,
            lcs_length=lcs_len,
            new_tool_errors=new_tool_errors,
            loop_regression=loop_regression,
            structural_output_drift=structural_output_drift,
            drift_reasons=drift_reasons,
            summary_markdown=summary_markdown,
            golden_steps=len(b_spans),
            candidate_steps=len(c_spans),
            tool_precision=round(precision, 4),
            tool_recall=round(recall, 4),
            tool_f1=round(f1, 4),
            argument_exact_match_rate=round(arg_exact_rate, 4),
            step_efficiency_ratio=round(efficiency, 4),
            golden_tokens=b_tokens,
            candidate_tokens=c_tokens,
            token_delta=c_tokens - b_tokens,
            golden_cost_usd=b_cost,
            candidate_cost_usd=c_cost,
            cost_delta_usd=round(c_cost - b_cost, 8),
            goal_completion_score=similarity_score,
            passed=not regression_detected,
        )


def compare_cassettes(
    baseline: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
    candidate: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
    *,
    similarity_threshold: float = 0.80,
    max_cost_increase_pct: float = 50.0,
    max_token_increase_pct: float = 50.0,
) -> TrajectoryDiffReport:
    """Compare a baseline cassette against a candidate cassette and detect behavioral regressions."""
    analyzer = TrajectoryDifferentialAnalyzer(
        similarity_threshold=similarity_threshold,
        max_cost_increase_pct=max_cost_increase_pct,
        max_token_increase_pct=max_token_increase_pct,
    )
    return analyzer.compare(baseline, candidate)
