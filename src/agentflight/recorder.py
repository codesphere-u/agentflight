"""
agentflight.recorder
====================
Black-Box Trajectory Flight Recorder & Deterministic Cassette Replayer.

Provides SHA-256 tamper-evident trajectory recording (`FlightRecorder`),
cryptographic cassette verification (`verify_cassette`), and sub-millisecond
$0.00 deterministic replay (`CassetteReplayer`) with structural diffing on
trajectory divergence (`TrajectoryDivergenceError`).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

SpanKind = Literal["llm_turn", "tool_call", "mcp_rpc", "state_checkpoint"]
SpanStatus = Literal["ok", "error", "skipped"]

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Serialize any JSON-compatible Python structure into a canonical string."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def canonical_hash(obj: Any) -> str:
    """Compute the SHA-256 hex digest of a canonical JSON payload."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


class CassetteTamperError(ValueError):
    """Raised when a recorded trajectory cassette fails SHA-256 hash chain verification."""


class TrajectoryDivergenceError(AssertionError):
    """Raised during deterministic replay when an agent step deviates from the golden cassette."""

    def __init__(
        self,
        message: str,
        *,
        step_index: int,
        expected_span: Optional["TrajectorySpan"] = None,
        actual_kind: Optional[str] = None,
        actual_actor: Optional[str] = None,
        actual_input: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.step_index = step_index
        self.expected_span = expected_span
        self.actual_kind = actual_kind
        self.actual_actor = actual_actor
        self.actual_input = actual_input
        self.diff = diff or {}


def _compute_payload_diff(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a structural diff between expected and actual dictionary payloads."""
    expected_keys = set(expected.keys())
    actual_keys = set(actual.keys())
    missing_keys = sorted(expected_keys - actual_keys)
    extra_keys = sorted(actual_keys - expected_keys)
    changed_values: Dict[str, Dict[str, Any]] = {}
    for k in sorted(expected_keys & actual_keys):
        if expected[k] != actual[k]:
            changed_values[k] = {"expected": expected[k], "actual": actual[k]}
    return {
        "missing_keys": missing_keys,
        "extra_keys": extra_keys,
        "changed_values": changed_values,
    }


@dataclass(frozen=True)
class TrajectorySpan:
    """Single immutable step in an AI agent's execution trajectory."""

    step_index: int
    kind: SpanKind
    actor: str
    input_payload: Dict[str, Any]
    output_payload: Dict[str, Any]
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    status: SpanStatus = "ok"
    prev_hash: str = GENESIS_HASH
    step_hash: str = ""
    input_hash: str = ""

    def compute_input_hash(self) -> str:
        """Compute canonical SHA-256 hash of `(kind, actor, input_payload)`."""
        return canonical_hash(
            {
                "kind": self.kind,
                "actor": self.actor,
                "input_payload": self.input_payload,
            }
        )

    def compute_step_hash(self) -> str:
        """Compute tamper-evident SHA-256 chain hash for this span."""
        envelope = {
            "step_index": self.step_index,
            "kind": self.kind,
            "actor": self.actor,
            "input_payload": self.input_payload,
            "output_payload": self.output_payload,
            "status": self.status,
            "prev_hash": self.prev_hash,
        }
        return canonical_hash(envelope)

    def with_computed_hashes(self, prev_hash: str) -> "TrajectorySpan":
        """Return a copy of this span with `prev_hash`, `input_hash`, and `step_hash` populated."""
        in_hash = self.compute_input_hash()
        provisional = TrajectorySpan(
            step_index=self.step_index,
            kind=self.kind,
            actor=self.actor,
            input_payload=self.input_payload,
            output_payload=self.output_payload,
            latency_ms=self.latency_ms,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=self.cost_usd,
            status=self.status,
            prev_hash=prev_hash,
            step_hash="",
            input_hash=in_hash,
        )
        s_hash = provisional.compute_step_hash()
        return TrajectorySpan(
            step_index=self.step_index,
            kind=self.kind,
            actor=self.actor,
            input_payload=self.input_payload,
            output_payload=self.output_payload,
            latency_ms=self.latency_ms,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=self.cost_usd,
            status=self.status,
            prev_hash=prev_hash,
            step_hash=s_hash,
            input_hash=in_hash,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectorySpan":
        return cls(
            step_index=int(data["step_index"]),
            kind=data["kind"],
            actor=str(data["actor"]),
            input_payload=dict(data.get("input_payload", {})),
            output_payload=dict(data.get("output_payload", {})),
            latency_ms=float(data.get("latency_ms", 0.0)),
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            status=data.get("status", "ok"),
            prev_hash=str(data.get("prev_hash", GENESIS_HASH)),
            step_hash=str(data.get("step_hash", "")),
            input_hash=str(data.get("input_hash", "")),
        )


class FlightRecorder:
    """
    Black-Box Flight Recorder for AI Agent execution trajectories.

    Records every LLM turn, MCP RPC, tool invocation, and state checkpoint into an
    append-only SHA-256 hash chain and persists `.flight.json` or `.flight.jsonl` cassettes.
    """

    def __init__(
        self,
        agent_id: str = "default-agent",
        metadata: Optional[Dict[str, Any]] = None,
        spans: Optional[Sequence[TrajectorySpan]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.metadata: Dict[str, Any] = dict(metadata or {})
        self._lock = threading.RLock()
        self._spans: List[TrajectorySpan] = []
        if spans:
            for sp in spans:
                self._append_verified(sp)

    def _append_verified(self, span: TrajectorySpan) -> TrajectorySpan:
        with self._lock:
            prev = self._spans[-1].step_hash if self._spans else GENESIS_HASH
            idx = len(self._spans)
            reindexed = TrajectorySpan(
                step_index=idx,
                kind=span.kind,
                actor=span.actor,
                input_payload=span.input_payload,
                output_payload=span.output_payload,
                latency_ms=span.latency_ms,
                prompt_tokens=span.prompt_tokens,
                completion_tokens=span.completion_tokens,
                cost_usd=span.cost_usd,
                status=span.status,
            ).with_computed_hashes(prev)
            self._spans.append(reindexed)
            return reindexed

    @property
    def spans(self) -> List[TrajectorySpan]:
        with self._lock:
            return list(self._spans)

    @property
    def head_hash(self) -> str:
        with self._lock:
            return self._spans[-1].step_hash if self._spans else GENESIS_HASH

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(s.prompt_tokens + s.completion_tokens for s in self._spans)

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return round(sum(s.cost_usd for s in self._spans), 8)

    @property
    def total_latency_ms(self) -> float:
        with self._lock:
            return round(sum(s.latency_ms for s in self._spans), 4)

    def record(
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
        status: SpanStatus = "ok",
    ) -> TrajectorySpan:
        """Record a single trajectory span and chain its SHA-256 digest thread-safely."""
        with self._lock:
            raw_span = TrajectorySpan(
                step_index=len(self._spans),
                kind=kind,
                actor=actor,
                input_payload=dict(input_payload),
                output_payload=dict(output_payload),
                latency_ms=float(latency_ms),
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                cost_usd=float(cost_usd),
                status=status,
            )
            return self._append_verified(raw_span)

    def wrap_tool(
        self,
        actor: str,
        fn: Callable[..., Dict[str, Any]],
        *,
        kind: SpanKind = "tool_call",
    ) -> Callable[..., Dict[str, Any]]:
        """Wrap a tool callable so every invocation is automatically recorded."""

        def _wrapped(**kwargs: Any) -> Dict[str, Any]:
            t0 = time.perf_counter()
            try:
                result = fn(**kwargs)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                self.record(
                    kind=kind,
                    actor=actor,
                    input_payload=kwargs,
                    output_payload=result,
                    latency_ms=elapsed_ms,
                    status="ok",
                )
                return result
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                self.record(
                    kind=kind,
                    actor=actor,
                    input_payload=kwargs,
                    output_payload={"error": str(exc), "error_type": type(exc).__name__},
                    latency_ms=elapsed_ms,
                    status="error",
                )
                raise

        return _wrapped

    def to_cassette_dict(self) -> Dict[str, Any]:
        """Serialize the full cassette into a dictionary with summary telemetry."""
        with self._lock:
            return {
                "version": "1.0.0",
                "agent_id": self.agent_id,
                "metadata": self.metadata,
                "head_hash": self.head_hash,
                "step_count": len(self._spans),
                "total_tokens": self.total_tokens,
                "total_cost_usd": self.total_cost_usd,
                "total_latency_ms": self.total_latency_ms,
                "spans": [s.to_dict() for s in self._spans],
            }

    def save(self, path: Union[str, Path]) -> Path:
        """
        Atomically save cassette to disk as `.flight.json` or `.flight.jsonl`.
        Automatically selects JSON Lines if the path ends with `.jsonl`.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if target.name.endswith(".jsonl"):
                lines: List[str] = []
                header = {
                    "type": "cassette_header",
                    "version": "1.0.0",
                    "agent_id": self.agent_id,
                    "metadata": self.metadata,
                    "head_hash": self.head_hash,
                    "step_count": len(self._spans),
                }
                lines.append(json.dumps(header, sort_keys=True))
                for sp in self._spans:
                    row = {"type": "span", **sp.to_dict()}
                    lines.append(json.dumps(row, sort_keys=True))
                payload_text = "\n".join(lines) + "\n"
            else:
                payload_text = json.dumps(self.to_cassette_dict(), indent=2, sort_keys=True) + "\n"

        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                handle.write(payload_text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        return target

    @classmethod
    def load(cls, path: Union[str, Path], *, verify: bool = True) -> "FlightRecorder":
        """Load a `.flight.json` or `.flight.jsonl` cassette and optionally verify its hash chain."""
        target = Path(path)
        try:
            raw_text = target.read_text(encoding="utf-8").strip()
            if target.name.endswith(".jsonl"):
                lines = [ln for ln in raw_text.splitlines() if ln.strip()]
                if not lines:
                    raise CassetteTamperError("Empty .flight.jsonl cassette file.")
                header = json.loads(lines[0])
                if not isinstance(header, dict) or header.get("type") != "cassette_header":
                    raise CassetteTamperError("Missing cassette_header in .flight.jsonl file.")
                spans = [TrajectorySpan.from_dict(json.loads(ln)) for ln in lines[1:]]
                cassette_dict = {
                    "version": header.get("version", "1.0.0"),
                    "agent_id": header.get("agent_id", "default-agent"),
                    "metadata": header.get("metadata", {}),
                    "head_hash": header.get("head_hash", GENESIS_HASH),
                    "step_count": header.get("step_count", len(spans)),
                    "spans": [s.to_dict() for s in spans],
                }
            else:
                cassette_dict = json.loads(raw_text)
                if not isinstance(cassette_dict, dict):
                    raise CassetteTamperError("Invalid cassette JSON: top-level value must be an object.")
                spans = [TrajectorySpan.from_dict(s) for s in cassette_dict.get("spans", [])]
        except CassetteTamperError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            raise CassetteTamperError(f"Malformed cassette file '{target}': {exc}") from exc

        if verify:
            verify_cassette(cassette_dict)

        recorder = cls(
            agent_id=cassette_dict.get("agent_id", "default-agent"),
            metadata=cassette_dict.get("metadata", {}),
        )
        recorder._spans = spans
        return recorder


def verify_cassette(cassette: Union[FlightRecorder, Dict[str, Any], Sequence[TrajectorySpan]]) -> bool:
    """
    Verify the cryptographic SHA-256 chain integrity of a recorded trajectory cassette.

    Raises `CassetteTamperError` if any step index, `prev_hash`, `input_hash`,
    `step_hash`, or `head_hash` has been modified or reordered.
    """
    expected_head: Optional[str] = None
    expected_count: Optional[int] = None

    if isinstance(cassette, FlightRecorder):
        spans = cassette.spans
        expected_head = cassette.head_hash
        expected_count = len(spans)
    elif isinstance(cassette, dict):
        spans = [
            s if isinstance(s, TrajectorySpan) else TrajectorySpan.from_dict(s)
            for s in cassette.get("spans", [])
        ]
        expected_head = cassette.get("head_hash")
        expected_count = cassette.get("step_count")
    else:
        spans = list(cassette)

    if expected_count is not None and expected_count != len(spans):
        raise CassetteTamperError(
            f"Step count mismatch: header declares {expected_count}, found {len(spans)} spans."
        )

    prev_hash = GENESIS_HASH
    for idx, span in enumerate(spans):
        if span.step_index != idx:
            raise CassetteTamperError(
                f"Non-sequential step_index at position {idx}: got {span.step_index}."
            )
        if span.prev_hash != prev_hash:
            raise CassetteTamperError(
                f"Broken prev_hash chain at step {idx}: expected {prev_hash}, got {span.prev_hash}."
            )
        recomputed_input_hash = span.compute_input_hash()
        if span.input_hash and span.input_hash != recomputed_input_hash:
            raise CassetteTamperError(
                f"Tampered input_payload at step {idx} ({span.actor}): "
                f"expected input_hash {span.input_hash}, computed {recomputed_input_hash}."
            )
        recomputed_step_hash = span.compute_step_hash()
        if span.step_hash != recomputed_step_hash:
            raise CassetteTamperError(
                f"Tampered span content at step {idx} ({span.actor}): "
                f"expected step_hash {span.step_hash}, computed {recomputed_step_hash}."
            )
        prev_hash = span.step_hash

    if expected_head is not None and expected_head != prev_hash:
        raise CassetteTamperError(
            f"Cassette head_hash mismatch: expected {expected_head}, computed {prev_hash}."
        )
    return True


class CassetteReplayer:
    """
    Deterministic Sub-Millisecond Cassette Replayer.

    Replays recorded LLM turns, MCP calls, and tool outputs with $0.00 API cost.
    Supports both:
    - `strict_order=True` (default): enforces exact step-by-step sequence and raises
      `TrajectoryDivergenceError` with a structural diff on the first mismatch.
    - `strict_order=False`: lookup-based stubbing by normalized `(kind, actor, canonical_input_hash)`.
    """

    def __init__(
        self,
        cassette: Union[FlightRecorder, Sequence[TrajectorySpan], str, Path],
        *,
        strict_order: bool = True,
    ) -> None:
        if isinstance(cassette, (str, Path)):
            recorder = FlightRecorder.load(cassette, verify=True)
            self._spans = recorder.spans
            self._agent_id = recorder.agent_id
        elif isinstance(cassette, FlightRecorder):
            verify_cassette(cassette)
            self._spans = cassette.spans
            self._agent_id = cassette.agent_id
        else:
            verify_cassette(cassette)
            self._spans = list(cassette)
            self._agent_id = "replayed-agent"

        self.strict_order = strict_order
        self._lock = threading.Lock()
        self._cursor: int = 0
        self._lookup: Dict[Tuple[str, str, str], List[TrajectorySpan]] = {}
        self._lookup_cursors: Dict[Tuple[str, str, str], int] = {}
        for sp in self._spans:
            key = (sp.kind, sp.actor, sp.compute_input_hash())
            self._lookup.setdefault(key, []).append(sp)
            self._lookup_cursors.setdefault(key, 0)

    @property
    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    @property
    def spans(self) -> List[TrajectorySpan]:
        """Return the sequence of recorded spans loaded in this cassette replayer."""
        return list(self._spans)

    @property
    def agent_id(self) -> str:
        """Return the recorded agent ID of the cassette."""
        return getattr(self, "_agent_id", "replayed-agent")

    @property
    def is_exhausted(self) -> bool:
        """True if the replay cursor has advanced through all spans in the cassette."""
        with self._lock:
            return self._cursor >= len(self._spans)

    def advance(self) -> TrajectorySpan:
        """Advance the replay cursor by one step and return that TrajectorySpan."""
        with self._lock:
            if self._cursor >= len(self._spans):
                raise StopIteration("CassetteReplayer cursor is exhausted.")
            span = self._spans[self._cursor]
            self._cursor += 1
            return span

    @property
    def remaining_steps(self) -> int:
        with self._lock:
            return max(0, len(self._spans) - self._cursor)

    @property
    def tokens_saved(self) -> int:
        with self._lock:
            return sum(s.prompt_tokens + s.completion_tokens for s in self._spans[: self._cursor])

    @property
    def cost_saved_usd(self) -> float:
        with self._lock:
            return round(sum(s.cost_usd for s in self._spans[: self._cursor]), 8)

    def reset(self) -> None:
        """Reset replay cursor back to step 0."""
        with self._lock:
            self._cursor = 0
            for k in self._lookup_cursors:
                self._lookup_cursors[k] = 0

    def replay_step(
        self,
        kind: SpanKind,
        actor: str,
        input_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Match an incoming agent call against the recorded cassette and return its output payload.

        Raises `TrajectoryDivergenceError` with a detailed structural diff if the call
        deviates from the recorded golden trajectory.
        """
        actual_in_hash = canonical_hash(
            {"kind": kind, "actor": actor, "input_payload": input_payload}
        )

        with self._lock:
            if self.strict_order:
                if self._cursor >= len(self._spans):
                    raise TrajectoryDivergenceError(
                        f"Trajectory exceeded recorded cassette length ({len(self._spans)} steps) "
                        f"with unexpected call {kind}:{actor}.",
                        step_index=self._cursor,
                        actual_kind=kind,
                        actual_actor=actor,
                        actual_input=input_payload,
                    )
                expected = self._spans[self._cursor]
                if (
                    expected.kind != kind
                    or expected.actor != actor
                    or expected.compute_input_hash() != actual_in_hash
                ):
                    diff = _compute_payload_diff(expected.input_payload, input_payload)
                    raise TrajectoryDivergenceError(
                        f"Trajectory divergence at step {self._cursor}: "
                        f"expected ({expected.kind}, '{expected.actor}') "
                        f"but got ({kind}, '{actor}'). Diff: {diff}",
                        step_index=self._cursor,
                        expected_span=expected,
                        actual_kind=kind,
                        actual_actor=actor,
                        actual_input=input_payload,
                        diff=diff,
                    )
                self._cursor += 1
                return dict(expected.output_payload)

            # Unordered lookup mode by (kind, actor, canonical_input_hash)
            key = (kind, actor, actual_in_hash)
            candidates = self._lookup.get(key)
            if not candidates:
                # Find closest actor match to produce an informative structural diff
                same_actor = [s for s in self._spans if s.kind == kind and s.actor == actor]
                expected_span = same_actor[0] if same_actor else None
                diff = (
                    _compute_payload_diff(expected_span.input_payload, input_payload)
                    if expected_span
                    else {}
                )
                raise TrajectoryDivergenceError(
                    f"No recorded cassette span matches ({kind}, '{actor}') with input {input_payload}.",
                    step_index=self._cursor,
                    expected_span=expected_span,
                    actual_kind=kind,
                    actual_actor=actor,
                    actual_input=input_payload,
                    diff=diff,
                )

            idx = self._lookup_cursors[key]
            chosen = candidates[min(idx, len(candidates) - 1)]
            self._lookup_cursors[key] = idx + 1
            self._cursor += 1
            return dict(chosen.output_payload)

    def stub_tool(self, actor: str, *, kind: SpanKind = "tool_call") -> Callable[..., Dict[str, Any]]:
        """Return a deterministic stub callable for `actor` backed by this cassette."""

        def _stub(**kwargs: Any) -> Dict[str, Any]:
            return self.replay_step(kind=kind, actor=actor, input_payload=kwargs)

        return _stub
