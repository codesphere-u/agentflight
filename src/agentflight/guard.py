"""
agentflight.guard
=================
Real-Time Trajectory Loop, Ping-Pong & Cost Circuit Breaker (`TrajectoryCircuitBreaker`).

Monitors live AI agent steps and trips a deterministic `CircuitBreakerTripped`
exception on:
1. Exact Call Loop (`(actor, canonical_input_hash)` repeated >= `max_identical_repeats` times consecutively).
2. Ping-Pong Oscillation (`A -> B -> A -> B` or 3-tool cycle `A -> B -> C -> A -> B -> C` without state progress).
3. Consecutive Tool Error Storm (`status == "error"` for >= `max_consecutive_errors` consecutive steps).
4. Token or USD Cost Budget Exceeded (`total_tokens > max_total_tokens` or `total_cost_usd > max_cost_usd`).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from .recorder import SpanKind, SpanStatus, TrajectorySpan, canonical_hash

TripReason = Literal[
    "exact_call_loop",
    "ping_pong_oscillation",
    "consecutive_error_storm",
    "token_budget_exceeded",
    "cost_budget_exceeded",
]


class CircuitBreakerTripped(RuntimeError):
    """Raised when `TrajectoryCircuitBreaker` detects a pathology or budget breach."""

    def __init__(
        self,
        message: str,
        *,
        reason: TripReason,
        step_index: int,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.step_index = step_index
        self.evidence = evidence or {}


@dataclass
class CircuitBreakerStats:
    """Live telemetry counters tracked by `TrajectoryCircuitBreaker`."""

    steps_observed: int = 0
    consecutive_errors: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    reserved_cost_usd: float = 0.0
    tripped: bool = False
    trip_reason: Optional[TripReason] = None
    trip_message: Optional[str] = None


class BudgetReservation:
    """
    Active budget reservation holding funds during in-flight LLM/tool execution.
    Prevents race conditions where parallel requests bypass spending caps.
    """

    def __init__(self, breaker: "TrajectoryCircuitBreaker", amount_usd: float) -> None:
        self.breaker = breaker
        self.amount_usd = amount_usd
        self._committed = False
        self._released = False

    def commit(self, actual_cost_usd: float) -> None:
        """Commit the reservation upon execution completion."""
        with self.breaker._lock:
            if not self._released and not self._committed:
                self.breaker.stats.reserved_cost_usd = max(
                    0.0, round(self.breaker.stats.reserved_cost_usd - self.amount_usd, 8)
                )
                self._committed = True

    def release(self) -> None:
        """Release reserved funds if execution was canceled, blocked, or failed before billing."""
        with self.breaker._lock:
            if not self._released and not self._committed:
                self.breaker.stats.reserved_cost_usd = max(
                    0.0, round(self.breaker.stats.reserved_cost_usd - self.amount_usd, 8)
                )
                self._released = True

    def __enter__(self) -> "BudgetReservation":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None and not self._committed:
            self.release()


class TrajectoryCircuitBreaker:
    """
    Real-Time Trajectory Loop, Ping-Pong & Cost Circuit Breaker.

    Can observe either raw parameters via `observe(...)` or `TrajectorySpan` instances
    via `observe_span(span)`.
    """

    def __init__(
        self,
        *,
        max_identical_repeats: int = 3,
        max_ping_pong_cycles: int = 2,
        max_consecutive_errors: int = 3,
        max_total_tokens: Optional[int] = 50_000,
        max_cost_usd: Optional[float] = 1.00,
    ) -> None:
        if max_identical_repeats < 2:
            raise ValueError("max_identical_repeats must be >= 2")
        if max_ping_pong_cycles < 2:
            raise ValueError("max_ping_pong_cycles must be >= 2")
        if max_consecutive_errors < 1:
            raise ValueError("max_consecutive_errors must be >= 1")

        self.max_identical_repeats = max_identical_repeats
        self.max_ping_pong_cycles = max_ping_pong_cycles
        self.max_consecutive_errors = max_consecutive_errors
        self.max_total_tokens = max_total_tokens
        self.max_cost_usd = max_cost_usd

        self._history: List[Tuple[str, str]] = []  # (actor, input_hash)
        self.stats = CircuitBreakerStats()
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset all circuit breaker counters and call history."""
        with self._lock:
            self._history.clear()
            self.stats = CircuitBreakerStats()

    def reserve_budget(self, estimated_cost_usd: float) -> BudgetReservation:
        """
        Thread-safe budget reservation for concurrent agent execution.
        Prevents race conditions where parallel requests bypass budget limits.
        """
        with self._lock:
            effective_total = self.stats.total_cost_usd + self.stats.reserved_cost_usd
            projected = effective_total + estimated_cost_usd
            if self.max_cost_usd is not None and projected > self.max_cost_usd:
                step_idx = self.stats.steps_observed
                self._trip(
                    reason="cost_budget_exceeded",
                    step_index=step_idx,
                    message=(
                        f"Budget reservation rejected at step {step_idx}: estimated ${estimated_cost_usd:.6f} "
                        f"with current spend ${self.stats.total_cost_usd:.6f} and active reservations ${self.stats.reserved_cost_usd:.6f} "
                        f"would total ${projected:.6f}, exceeding cap ${self.max_cost_usd:.4f}."
                    ),
                    evidence={
                        "estimated_cost_usd": estimated_cost_usd,
                        "current_spent_usd": self.stats.total_cost_usd,
                        "reserved_cost_usd": self.stats.reserved_cost_usd,
                        "projected_total_usd": projected,
                        "budget_limit_usd": self.max_cost_usd,
                    },
                )
            self.stats.reserved_cost_usd = round(self.stats.reserved_cost_usd + estimated_cost_usd, 8)
            return BudgetReservation(self, estimated_cost_usd)

    def observe_span(self, span: TrajectorySpan) -> CircuitBreakerStats:
        """Inspect a recorded `TrajectorySpan` and trip if any guard invariant is violated."""
        return self.observe(
            actor=span.actor,
            input_payload=span.input_payload,
            status=span.status,
            prompt_tokens=span.prompt_tokens,
            completion_tokens=span.completion_tokens,
            cost_usd=span.cost_usd,
            kind=span.kind,
        )

    def observe(
        self,
        actor: str,
        input_payload: Dict[str, Any],
        *,
        status: SpanStatus = "ok",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        kind: SpanKind = "tool_call",
    ) -> CircuitBreakerStats:
        """
        Inspect a live agent step and raise `CircuitBreakerTripped` if any threshold is breached.
        """
        with self._lock:
            step_idx = self.stats.steps_observed
            self.stats.steps_observed += 1
            self.stats.total_tokens += int(prompt_tokens) + int(completion_tokens)
            self.stats.total_cost_usd = round(self.stats.total_cost_usd + float(cost_usd), 8)

        if status == "error":
            self.stats.consecutive_errors += 1
        else:
            self.stats.consecutive_errors = 0

        # 1. Token budget check
        if self.max_total_tokens is not None and self.stats.total_tokens > self.max_total_tokens:
            self._trip(
                reason="token_budget_exceeded",
                step_index=step_idx,
                message=(
                    f"Token budget exceeded at step {step_idx}: "
                    f"{self.stats.total_tokens} tokens > cap {self.max_total_tokens}."
                ),
                evidence={
                    "total_tokens": self.stats.total_tokens,
                    "max_total_tokens": self.max_total_tokens,
                    "actor": actor,
                },
            )

        # 2. Cost budget check
        if self.max_cost_usd is not None and self.stats.total_cost_usd > self.max_cost_usd:
            self._trip(
                reason="cost_budget_exceeded",
                step_index=step_idx,
                message=(
                    f"USD cost budget exceeded at step {step_idx}: "
                    f"${self.stats.total_cost_usd:.4f} > cap ${self.max_cost_usd:.4f}."
                ),
                evidence={
                    "total_cost_usd": self.stats.total_cost_usd,
                    "max_cost_usd": self.max_cost_usd,
                    "actor": actor,
                },
            )

        # 3. Consecutive error storm check
        if self.stats.consecutive_errors >= self.max_consecutive_errors:
            self._trip(
                reason="consecutive_error_storm",
                step_index=step_idx,
                message=(
                    f"Consecutive tool error storm at step {step_idx}: "
                    f"{self.stats.consecutive_errors} failed invocations in a row (last actor: '{actor}')."
                ),
                evidence={
                    "consecutive_errors": self.stats.consecutive_errors,
                    "max_consecutive_errors": self.max_consecutive_errors,
                    "actor": actor,
                },
            )

        # Track tool/MCP call signatures for loop & ping-pong detection
        sig = (actor, canonical_hash(input_payload))
        self._history.append(sig)

        # 4. Exact Call Loop check: N identical (actor, canonical_args) calls in a row
        n_rep = self.max_identical_repeats
        if len(self._history) >= n_rep:
            tail = self._history[-n_rep:]
            if all(item == sig for item in tail):
                self._trip(
                    reason="exact_call_loop",
                    step_index=step_idx,
                    message=(
                        f"Exact call loop detected at step {step_idx}: tool '{actor}' invoked "
                        f"{n_rep} times consecutively with identical arguments."
                    ),
                    evidence={
                        "actor": actor,
                        "repeats": n_rep,
                        "input_payload": input_payload,
                    },
                )

        # 5. Ping-Pong Oscillation check: cycle period k in (2, 3) repeated `max_ping_pong_cycles` times
        for period in (2, 3):
            window_len = period * self.max_ping_pong_cycles
            if len(self._history) >= window_len:
                window = self._history[-window_len:]
                pattern = window[:period]
                # Ensure the pattern has at least 2 distinct signatures so it's a true oscillation
                if len(set(pattern)) >= 2:
                    is_periodic = all(
                        window[i] == pattern[i % period] for i in range(window_len)
                    )
                    if is_periodic:
                        cycle_actors = [p[0] for p in pattern]
                        cycle_str = " -> ".join(cycle_actors * self.max_ping_pong_cycles)
                        self._trip(
                            reason="ping_pong_oscillation",
                            step_index=step_idx,
                            message=(
                                f"Ping-pong oscillation detected at step {step_idx}: "
                                f"cycle ({cycle_str}) repeated {self.max_ping_pong_cycles} times without progress."
                            ),
                            evidence={
                                "period": period,
                                "cycles": self.max_ping_pong_cycles,
                                "pattern_actors": cycle_actors,
                            },
                        )

        return self.stats

    def _trip(
        self,
        *,
        reason: TripReason,
        step_index: int,
        message: str,
        evidence: Dict[str, Any],
    ) -> None:
        self.stats.tripped = True
        self.stats.trip_reason = reason
        self.stats.trip_message = message
        raise CircuitBreakerTripped(
            message,
            reason=reason,
            step_index=step_index,
            evidence=evidence,
        )
