"""
agentflight.eval
================
Trajectory Diff & Golden Evaluation Engine (`TrajectoryEvaluator`).

Compares a candidate agent trajectory against a golden reference trajectory,
computing:
- Tool Selection Precision, Recall, and F1
- Argument Exact-Match Accuracy
- Trajectory Step Efficiency Ratio
- Token & USD Cost Deltas
- Goal Completion Score (0.0 - 1.0)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from .recorder import FlightRecorder, TrajectorySpan, canonical_hash


def _extract_spans(source: Union[FlightRecorder, Sequence[TrajectorySpan]]) -> List[TrajectorySpan]:
    if isinstance(source, FlightRecorder):
        return source.spans
    return list(source)


@dataclass(frozen=True)
class StepDiffItem:
    """Structural comparison of a single step index or unmatched span."""

    index: int
    status: str  # "exact_match", "arg_mismatch", "actor_mismatch", "extra_step", "missing_step"
    golden_actor: Optional[str] = None
    candidate_actor: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrajectoryDiffReport:
    """Comprehensive evaluation report comparing a candidate trajectory to a golden trajectory."""

    golden_steps: int
    candidate_steps: int
    tool_precision: float
    tool_recall: float
    tool_f1: float
    argument_exact_match_rate: float
    step_efficiency_ratio: float
    golden_tokens: int
    candidate_tokens: int
    token_delta: int
    golden_cost_usd: float
    candidate_cost_usd: float
    cost_delta_usd: float
    goal_completion_score: float
    passed: bool
    step_diffs: List[StepDiffItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
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
            "step_diffs": [d.to_dict() for d in self.step_diffs],
        }


class TrajectoryEvaluator:
    """
    Evaluates candidate agent trajectories against golden reference cassettes.
    """

    def __init__(self, *, pass_threshold: float = 0.85) -> None:
        self.pass_threshold = pass_threshold

    def diff_trajectories(
        self,
        golden: Union[FlightRecorder, Sequence[TrajectorySpan]],
        candidate: Union[FlightRecorder, Sequence[TrajectorySpan]],
    ) -> TrajectoryDiffReport:
        """
        Compare `candidate` trajectory against `golden` trajectory and compute precision,
        recall, efficiency ratio, token/cost deltas, and overall goal completion score.
        """
        g_spans = _extract_spans(golden)
        c_spans = _extract_spans(candidate)

        # Filter tool/MCP invocations for tool selection metrics (or fall back to all spans)
        g_tools = [s for s in g_spans if s.kind in ("tool_call", "mcp_rpc")] or g_spans
        c_tools = [s for s in c_spans if s.kind in ("tool_call", "mcp_rpc")] or c_spans

        g_actor_counts = Counter(s.actor for s in g_tools)
        c_actor_counts = Counter(s.actor for s in c_tools)

        matched_actors = sum((g_actor_counts & c_actor_counts).values())
        total_g_tools = sum(g_actor_counts.values())
        total_c_tools = sum(c_actor_counts.values())

        precision = matched_actors / total_c_tools if total_c_tools > 0 else (1.0 if total_g_tools == 0 else 0.0)
        recall = matched_actors / total_g_tools if total_g_tools > 0 else (1.0 if total_c_tools == 0 else 0.0)
        f1 = (
            (2.0 * precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Exact signature match (actor + canonical input_payload)
        g_sig_counts = Counter((s.actor, canonical_hash(s.input_payload)) for s in g_tools)
        c_sig_counts = Counter((s.actor, canonical_hash(s.input_payload)) for s in c_tools)
        exact_sig_matches = sum((g_sig_counts & c_sig_counts).values())
        arg_exact_rate = (
            exact_sig_matches / total_g_tools if total_g_tools > 0 else 1.0
        )

        # Step efficiency ratio: 1.0 when candidate_steps == golden_steps, penalized when bloated
        if len(c_spans) == 0 and len(g_spans) == 0:
            efficiency = 1.0
        elif len(c_spans) == 0:
            efficiency = 0.0
        else:
            efficiency = min(1.0, len(g_spans) / len(c_spans))

        # Token & Cost Deltas
        g_tokens = sum(s.prompt_tokens + s.completion_tokens for s in g_spans)
        c_tokens = sum(s.prompt_tokens + s.completion_tokens for s in c_spans)
        g_cost = round(sum(s.cost_usd for s in g_spans), 8)
        c_cost = round(sum(s.cost_usd for s in c_spans), 8)

        # Final output / state agreement bonus
        final_match = 0.0
        if g_spans and c_spans:
            g_last = g_spans[-1]
            c_last = c_spans[-1]
            if (
                c_last.status == "ok"
                and g_last.actor == c_last.actor
                and canonical_hash(g_last.output_payload) == canonical_hash(c_last.output_payload)
            ):
                final_match = 1.0
            elif c_last.status == "ok":
                final_match = 0.5
        elif not g_spans and not c_spans:
            final_match = 1.0

        # Composite Goal Completion Score in [0.0, 1.0]
        goal_score = round(
            0.35 * f1
            + 0.30 * arg_exact_rate
            + 0.15 * efficiency
            + 0.20 * final_match,
            4,
        )

        # Step-by-step structural comparison
        step_diffs: List[StepDiffItem] = []
        max_len = max(len(g_spans), len(c_spans))
        for idx in range(max_len):
            if idx >= len(g_spans):
                c_sp = c_spans[idx]
                step_diffs.append(
                    StepDiffItem(
                        index=idx,
                        status="extra_step",
                        golden_actor=None,
                        candidate_actor=c_sp.actor,
                        detail=f"Candidate executed extra step '{c_sp.actor}'.",
                    )
                )
            elif idx >= len(c_spans):
                g_sp = g_spans[idx]
                step_diffs.append(
                    StepDiffItem(
                        index=idx,
                        status="missing_step",
                        golden_actor=g_sp.actor,
                        candidate_actor=None,
                        detail=f"Candidate omitted golden step '{g_sp.actor}'.",
                    )
                )
            else:
                g_sp = g_spans[idx]
                c_sp = c_spans[idx]
                if g_sp.actor != c_sp.actor:
                    step_diffs.append(
                        StepDiffItem(
                            index=idx,
                            status="actor_mismatch",
                            golden_actor=g_sp.actor,
                            candidate_actor=c_sp.actor,
                            detail=f"Expected actor '{g_sp.actor}', got '{c_sp.actor}'.",
                        )
                    )
                elif canonical_hash(g_sp.input_payload) != canonical_hash(c_sp.input_payload):
                    step_diffs.append(
                        StepDiffItem(
                            index=idx,
                            status="arg_mismatch",
                            golden_actor=g_sp.actor,
                            candidate_actor=c_sp.actor,
                            detail=f"Actor '{g_sp.actor}' called with different arguments.",
                        )
                    )
                else:
                    step_diffs.append(
                        StepDiffItem(
                            index=idx,
                            status="exact_match",
                            golden_actor=g_sp.actor,
                            candidate_actor=c_sp.actor,
                            detail="Exact step match.",
                        )
                    )

        return TrajectoryDiffReport(
            golden_steps=len(g_spans),
            candidate_steps=len(c_spans),
            tool_precision=round(precision, 4),
            tool_recall=round(recall, 4),
            tool_f1=round(f1, 4),
            argument_exact_match_rate=round(arg_exact_rate, 4),
            step_efficiency_ratio=round(efficiency, 4),
            golden_tokens=g_tokens,
            candidate_tokens=c_tokens,
            token_delta=c_tokens - g_tokens,
            golden_cost_usd=g_cost,
            candidate_cost_usd=c_cost,
            cost_delta_usd=round(c_cost - g_cost, 8),
            goal_completion_score=goal_score,
            passed=goal_score >= self.pass_threshold,
            step_diffs=step_diffs,
        )


def diff_trajectories(
    golden: Union[FlightRecorder, Sequence[TrajectorySpan]],
    candidate: Union[FlightRecorder, Sequence[TrajectorySpan]],
    *,
    pass_threshold: float = 0.85,
) -> TrajectoryDiffReport:
    """Convenience function wrapping `TrajectoryEvaluator.diff_trajectories`."""
    return TrajectoryEvaluator(pass_threshold=pass_threshold).diff_trajectories(golden, candidate)
