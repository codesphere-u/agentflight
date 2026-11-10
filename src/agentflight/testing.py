"""
agentflight.testing
===================
Deterministic VCR Record/Replay Testing Fixture & Decorator for AI Agents.

Eliminates the cost, non-determinism, and network latency of LLM APIs
in CI/CD pipelines by recording agent trajectories to cryptographic cassettes
and replaying them in sub-microseconds (<3 μs P50).
"""

from __future__ import annotations

import functools
import inspect
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Union

from .diff import TrajectoryDifferentialAnalyzer, compare_cassettes
from .recorder import (
    CassetteReplayer,
    FlightRecorder,
    SpanKind,
    TrajectoryDivergenceError,
    TrajectorySpan,
    verify_cassette,
)

RecordMode = Literal["auto", "record", "replay", "diff"]


class FlightSession:
    """
    Active testing session managing record/replay state for an agent test.
    
    Can be used directly as a context manager:
    >>> with FlightSession("tests/fixtures/search.cassette.json") as flight:
    ...     stubbed_tool = flight.stub("search_db")
    ...     result = stubbed_tool(q="revenue 2026")
    """

    def __init__(
        self,
        cassette_path: Union[str, Path],
        *,
        mode: RecordMode = "auto",
        agent_id: str = "test-agent",
        metadata: Optional[Dict[str, Any]] = None,
        fail_on_drift: bool = True,
    ) -> None:
        self.cassette_path = Path(cassette_path)
        self.mode: RecordMode = mode
        self.agent_id = agent_id
        self.metadata = metadata or {}
        self.fail_on_drift = fail_on_drift

        # Determine effective mode if "auto"
        if self.mode == "auto":
            self.effective_mode: Literal["replay", "record"] = (
                "replay" if self.cassette_path.exists() else "record"
            )
        else:
            self.effective_mode = "replay" if self.mode == "replay" else "record"

        self.recorder: FlightRecorder = FlightRecorder(
            agent_id=self.agent_id,
            metadata={**self.metadata, "test_session": True},
        )
        self.replayer: Optional[CassetteReplayer] = None
        self._initial_cassette_dict: Optional[Dict[str, Any]] = None

        if self.effective_mode == "replay" or self.mode == "diff":
            if not self.cassette_path.exists():
                raise FileNotFoundError(
                    f"Cassette file not found at {self.cassette_path} for replay mode."
                )
            with open(self.cassette_path, "r", encoding="utf-8") as f:
                self._initial_cassette_dict = json.load(f)
            self.replayer = CassetteReplayer(self.cassette_path)

    @property
    def is_replaying(self) -> bool:
        """True if currently replaying from an existing cassette."""
        return self.effective_mode == "replay"

    @property
    def is_recording(self) -> bool:
        """True if currently recording live spans."""
        return self.effective_mode == "record"

    @property
    def spans(self) -> Sequence[TrajectorySpan]:
        """All recorded spans in the current session."""
        return self.recorder.spans

    @property
    def step_count(self) -> int:
        """Number of spans recorded in this session."""
        return len(self.recorder.spans)

    @property
    def total_cost_usd(self) -> float:
        """Total financial cost in USD across all recorded spans."""
        return self.recorder.total_cost_usd()

    @property
    def total_tokens(self) -> int:
        """Total token count across all recorded spans."""
        return self.recorder.total_tokens()

    def record_step(
        self,
        kind: SpanKind,
        actor: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        *,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        status: Literal["ok", "error", "skipped"] = "ok",
    ) -> TrajectorySpan:
        """Manually record a span into the session."""
        return self.recorder.record(
            kind,
            actor,
            input_payload,
            output_payload,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            status=status,
        )

    def stub(
        self,
        actor: str,
        *,
        kind: SpanKind = "tool_call",
        fallback_fn: Optional[Callable[..., Any]] = None,
    ) -> Callable[..., Any]:
        """
        Return a deterministic callable for an actor/tool.
        
        In replay mode: Returns output payload from the recorded cassette.
        In record mode: Invokes `fallback_fn` (or mock) and records the span.
        """
        if self.is_replaying and self.replayer is not None:
            return self.replayer.stub_tool(actor, kind=kind)

        # In record mode
        def _recording_stub(**kwargs: Any) -> Any:
            if fallback_fn is not None:
                out = fallback_fn(**kwargs)
            else:
                out = {"status": "ok", "mock_actor": actor, "args": kwargs}
            out_dict = out if isinstance(out, dict) else {"result": out}
            self.recorder.record(
                kind,
                actor,
                kwargs,
                out_dict,
                latency_ms=0.5,
                status="ok",
            )
            return out

        return _recording_stub

    def wrap(
        self,
        fn: Callable[..., Any],
        *,
        actor: Optional[str] = None,
        kind: SpanKind = "tool_call",
    ) -> Callable[..., Any]:
        """
        Wrap an existing real function/tool callable with flight recorder interception.
        
        In replay mode: Dispatches to cassette stub without executing live function.
        In record mode: Runs the live function, captures execution, and records span.
        """
        actor_name = actor or fn.__name__

        @functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            call_kwargs = dict(kwargs)
            if args:
                call_kwargs["_args"] = list(args)

            if self.is_replaying and self.replayer is not None:
                out = self.replayer.replay_step(kind=kind, actor=actor_name, input_payload=call_kwargs)
                return out

            # Live execution
            out = fn(*args, **kwargs)
            out_dict = out if isinstance(out, dict) else {"result": out}
            self.recorder.record(
                kind,
                actor_name,
                call_kwargs,
                out_dict,
                latency_ms=1.0,
                status="ok",
            )
            return out

        return _wrapper

    def __enter__(self) -> FlightSession:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            return

        # If recording or diff mode, save/verify cassette
        if self.effective_mode == "record":
            self.cassette_path.parent.mkdir(parents=True, exist_ok=True)
            self.recorder.save(self.cassette_path)

        elif self.mode == "diff" and self._initial_cassette_dict is not None:
            candidate_dict = self.recorder.to_cassette_dict()
            report = compare_cassettes(self._initial_cassette_dict, candidate_dict)
            if self.fail_on_drift and not report.is_identical:
                diff_summary = "\n".join(report.summary_lines)
                raise TrajectoryDivergenceError(
                    f"Trajectory drifted from baseline cassette {self.cassette_path}:\n{diff_summary}"
                )


def flight_test(
    cassette: Union[str, Path],
    *,
    mode: RecordMode = "auto",
    agent_id: str = "test-agent",
    fail_on_drift: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for pytest test functions enabling deterministic VCR agent testing.
    
    Usage:
    >>> @flight_test("tests/fixtures/weather.cassette.json")
    ... def test_weather_agent(flight):
    ...     tool = flight.stub("get_weather")
    ...     resp = tool(city="Tokyo")
    ...     assert "temperature" in resp
    """

    def _decorator(test_fn: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(test_fn)
        wants_flight = "flight" in sig.parameters

        @functools.wraps(test_fn)
        def _run_test(*args: Any, **kwargs: Any) -> Any:
            with FlightSession(
                cassette,
                mode=mode,
                agent_id=agent_id,
                fail_on_drift=fail_on_drift,
            ) as session:
                if wants_flight:
                    kwargs["flight"] = session
                return test_fn(*args, **kwargs)

        return _run_test

    return _decorator
