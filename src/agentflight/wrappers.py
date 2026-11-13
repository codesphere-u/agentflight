"""
agentflight.wrappers
====================
1-Line Drop-In SDK Wrappers for OpenAI, Anthropic, OpenRouter, vLLM, OpenAny,
and LangGraph / generic agent callables.

Wraps any standard client or function with:
1. Pre-execution budget reservation (`TrajectoryCircuitBreaker.reserve_budget`)
2. Tamper-evident SHA-256 flight recording (`FlightRecorder`)
3. Loop, ping-pong, error, and token circuit breaking (`TrajectoryCircuitBreaker.observe_span`)
4. Zero-cost offline deterministic replay (`CassetteReplayer`)

Pure Python standard library — works with any SDK via duck typing without adding
heavy client dependencies to `agentflight-mcp`.
"""

from __future__ import annotations

import functools
import inspect
import threading
import time
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, cast

from agentflight.guard import BudgetReservation, TrajectoryCircuitBreaker
from agentflight.recorder import CassetteReplayer, FlightRecorder, SpanKind

# Conservative USD per 1M tokens: (prompt_per_1m, completion_per_1m)
DEFAULT_MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "o3-mini": (1.10, 4.40),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}
_FALLBACK_PRICING: Tuple[float, float] = (1.00, 3.00)


class _ReplayNode(SimpleNamespace):
    """Attribute- and dict-compatible proxy returned when replaying serialized LLM objects."""

    def model_dump(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], _to_plain_value(self))

    def to_dict(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], _to_plain_value(self))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _to_plain_value(obj: Any) -> Any:
    """Convert Pydantic models, dataclasses, namespaces, and containers into JSON-safe Python types."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _to_plain_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain_value(item) for item in obj]
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return _to_plain_value(obj.model_dump())
    if hasattr(obj, "dict") and callable(obj.dict) and not isinstance(obj, type):
        return _to_plain_value(obj.dict())
    if hasattr(obj, "__dict__"):
        return {
            str(k): _to_plain_value(v)
            for k, v in vars(obj).items()
            if not str(k).startswith("_") and not callable(v)
        }
    return str(obj)


def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    """Ensure top-level payload is always a dictionary for canonical span hashing."""
    converted = _to_plain_value(obj)
    if isinstance(converted, dict):
        return converted
    return {"value": converted}


def _reconstruct_replay_object(value: Any) -> Any:
    """Reconstruct nested attribute-accessible `_ReplayNode` structures from a dict payload."""
    if isinstance(value, dict):
        return _ReplayNode(**{k: _reconstruct_replay_object(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_reconstruct_replay_object(v) for v in value]
    return value


def _estimate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    model_pricing: Optional[Mapping[str, Tuple[float, float]]] = None,
) -> float:
    """Compute token cost in USD from explicit pricing overrides or prefix-matched defaults."""
    pricing_table = dict(DEFAULT_MODEL_PRICING)
    if model_pricing:
        pricing_table.update(model_pricing)

    normalized = (model or "").lower()
    # Match longest key first so e.g. gpt-4o-mini beats gpt-4o
    rates = _FALLBACK_PRICING
    if normalized in pricing_table:
        rates = pricing_table[normalized]
    else:
        for prefix in sorted(pricing_table, key=len, reverse=True):
            if prefix.lower() in normalized:
                rates = pricing_table[prefix]
                break

    in_rate, out_rate = rates
    cost = (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0
    return round(cost, 8)


def _extract_usage_tokens(response_dict: Dict[str, Any]) -> Tuple[int, int, Optional[float]]:
    """Extract (prompt_tokens, completion_tokens, explicit_cost_usd) across OpenAI/Anthropic shapes."""
    usage = response_dict.get("usage")
    if not isinstance(usage, Mapping):
        return 0, 0, None

    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    explicit_cost = usage.get("cost")
    if explicit_cost is None:
        explicit_cost = usage.get("cost_usd")
    return prompt_tokens, completion_tokens, (float(explicit_cost) if explicit_cost is not None else None)


def _attach_agentflight_handles(
    target: Any,
    recorder: FlightRecorder,
    guard: TrajectoryCircuitBreaker,
    replayer: Optional[CassetteReplayer],
) -> None:
    """Expose underlying AgentFlight telemetry handles on any wrapped client or callable."""
    setattr(target, "agentflight_recorder", recorder)
    setattr(target, "agentflight_guard", guard)
    setattr(target, "agentflight_replayer", replayer)


def wrap_callable(
    fn: Callable[..., Any],
    *,
    kind: SpanKind = "tool_call",
    actor: Optional[str] = None,
    recorder: Optional[FlightRecorder] = None,
    guard: Optional[TrajectoryCircuitBreaker] = None,
    replayer: Optional[CassetteReplayer] = None,
    estimated_cost_usd: float = 0.0,
) -> Callable[..., Any]:
    """
    Wrap any synchronous or asynchronous tool/node/LLM callable with AgentFlight telemetry & guards.

    Exposes `.agentflight_recorder` and `.agentflight_guard` attributes on the returned wrapper.
    """
    resolved_actor: str = str(actor or getattr(fn, "__name__", None) or "wrapped_callable")
    rec = recorder or FlightRecorder(agent_id=resolved_actor)
    breaker = guard or TrajectoryCircuitBreaker()

    def _build_input(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = _to_plain_dict(kwargs)
        if args:
            payload["_args"] = [_to_plain_value(a) for a in args]
        return payload

    def _record_and_observe_ok(
        input_payload: Dict[str, Any],
        result: Any,
        elapsed_ms: float,
    ) -> None:
        span = rec.record(
            kind=kind,
            actor=resolved_actor,
            input_payload=input_payload,
            output_payload=_to_plain_dict(result),
            latency_ms=elapsed_ms,
            cost_usd=estimated_cost_usd,
            status="ok",
        )
        breaker.observe_span(span)

    def _record_and_observe_err(
        input_payload: Dict[str, Any],
        exc: Exception,
        elapsed_ms: float,
    ) -> None:
        span = rec.record(
            kind=kind,
            actor=resolved_actor,
            input_payload=input_payload,
            output_payload={"error": str(exc), "error_type": type(exc).__name__},
            latency_ms=elapsed_ms,
            status="error",
        )
        breaker.observe_span(span)

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            input_payload = _build_input(args, kwargs)
            if replayer is not None:
                replayed = replayer.replay_step(kind, resolved_actor, input_payload)
                return replayed.get("value", replayed) if list(replayed.keys()) == ["value"] else replayed

            t0 = time.perf_counter()
            with breaker.reserve_budget(estimated_cost_usd) as reservation:
                try:
                    result = await fn(*args, **kwargs)
                    reservation.commit(estimated_cost_usd)
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    _record_and_observe_err(input_payload, exc, elapsed_ms)
                    raise
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _record_and_observe_ok(input_payload, result, elapsed_ms)
            return result

        _attach_agentflight_handles(_async_wrapper, rec, breaker, replayer)
        return _async_wrapper

    @functools.wraps(fn)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        input_payload = _build_input(args, kwargs)
        if replayer is not None:
            replayed = replayer.replay_step(kind, resolved_actor, input_payload)
            return replayed.get("value", replayed) if list(replayed.keys()) == ["value"] else replayed

        t0 = time.perf_counter()
        with breaker.reserve_budget(estimated_cost_usd) as reservation:
            try:
                result = fn(*args, **kwargs)
                reservation.commit(estimated_cost_usd)
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                _record_and_observe_err(input_payload, exc, elapsed_ms)
                raise
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _record_and_observe_ok(input_payload, result, elapsed_ms)
        return result

    _attach_agentflight_handles(_sync_wrapper, rec, breaker, replayer)
    return _sync_wrapper


class _NamespaceProxy:
    """Lightweight attribute proxy that preserves the wrapped client's full interface."""

    def __init__(self, target: Any, **overrides: Any) -> None:
        self._target = target
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._target, name)


def _merge_tool_call_deltas(deltas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Coalesce OpenAI-style streamed tool_call deltas by index into complete tool calls."""
    merged: Dict[int, Dict[str, Any]] = {}
    for item in deltas:
        raw_idx = item.get("index")
        idx = int(raw_idx) if isinstance(raw_idx, int) else (max(merged.keys()) + 1 if merged else 0)
        entry = merged.setdefault(
            idx,
            {"index": idx, "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if item.get("id"):
            entry["id"] = item["id"]
        if item.get("type"):
            entry["type"] = item["type"]
        fn = item.get("function")
        if isinstance(fn, Mapping):
            fn_entry = entry["function"]
            if fn.get("name"):
                fn_entry["name"] = str(fn["name"])
            if fn.get("arguments"):
                fn_entry["arguments"] = f"{fn_entry['arguments']}{fn['arguments']}"
    return [merged[k] for k in sorted(merged)]


class _StreamAccumulator:
    """Shared accumulator for OpenAI / Anthropic / Responses streaming responses."""

    def __init__(
        self,
        *,
        actor: str,
        model: str,
        input_payload: Dict[str, Any],
        recorder: FlightRecorder,
        guard: TrajectoryCircuitBreaker,
        reservation: BudgetReservation,
        model_pricing: Optional[Mapping[str, Tuple[float, float]]],
        t0: float,
    ) -> None:
        self.actor = actor
        self.model = model
        self.input_payload = input_payload
        self.recorder = recorder
        self.guard = guard
        self.reservation = reservation
        self.model_pricing = model_pricing
        self.t0 = t0
        self.text_parts: List[str] = []
        self.chunk_count = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.explicit_cost: Optional[float] = None
        self.tool_call_deltas: List[Dict[str, Any]] = []
        self._finalized = False

    def observe_chunk(self, chunk: Any) -> None:
        self.chunk_count += 1
        chunk_dict = _to_plain_dict(chunk)

        # Extract token usage across OpenAI Chat, Responses, and Anthropic SSE events
        pt, ct, ec = _extract_usage_tokens(chunk_dict)
        if pt:
            self.prompt_tokens = pt
        if ct:
            self.completion_tokens = ct
        if ec is not None:
            self.explicit_cost = ec

        message = chunk_dict.get("message")
        if isinstance(message, Mapping):
            mpt, mct, mec = _extract_usage_tokens(dict(message))
            if mpt:
                self.prompt_tokens = mpt
            if mct:
                self.completion_tokens = mct
            if mec is not None:
                self.explicit_cost = mec

        resp_obj = chunk_dict.get("response")
        if isinstance(resp_obj, Mapping):
            rpt, rct, rec = _extract_usage_tokens(dict(resp_obj))
            if rpt:
                self.prompt_tokens = rpt
            if rct:
                self.completion_tokens = rct
            if rec is not None:
                self.explicit_cost = rec

        # Extract streamed text deltas
        choices = chunk_dict.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], Mapping) else {}
            raw_delta = first.get("delta")
            delta_map: Mapping[str, Any] = raw_delta if isinstance(raw_delta, Mapping) else {}
            content = delta_map.get("content")
            if isinstance(content, str):
                self.text_parts.append(content)
            tc = delta_map.get("tool_calls")
            if isinstance(tc, list):
                for item in tc:
                    if isinstance(item, Mapping):
                        self.tool_call_deltas.append(dict(item))
            return

        delta = chunk_dict.get("delta")
        if isinstance(delta, str):
            self.text_parts.append(delta)
        elif isinstance(delta, Mapping):
            for key in ("text", "partial_json"):
                val = delta.get(key)
                if isinstance(val, str):
                    self.text_parts.append(val)

    def finalize_ok(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        full_text = "".join(self.text_parts)
        pt = self.prompt_tokens
        ct = self.completion_tokens or (max(1, len(full_text) // 4) if full_text else 0)
        resolved_cost = (
            self.explicit_cost
            if self.explicit_cost is not None
            else _estimate_cost_usd(self.model, pt, ct, model_pricing=self.model_pricing)
        )
        self.reservation.commit(resolved_cost)
        output_payload: Dict[str, Any] = {
            "text": full_text,
            "chunks": self.chunk_count,
            "stream": True,
            "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct},
        }
        if self.tool_call_deltas:
            output_payload["tool_calls"] = _merge_tool_call_deltas(self.tool_call_deltas)

        span = self.recorder.record(
            kind="llm_turn",
            actor=self.actor,
            input_payload=self.input_payload,
            output_payload=output_payload,
            latency_ms=(time.perf_counter() - self.t0) * 1000.0,
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=resolved_cost,
            status="ok",
        )
        self.guard.observe_span(span)

    def finalize_error(self, exc: BaseException) -> None:
        if self._finalized:
            return
        self._finalized = True
        self.reservation.release()
        span = self.recorder.record(
            kind="llm_turn",
            actor=self.actor,
            input_payload=self.input_payload,
            output_payload={
                "error": str(exc),
                "error_type": type(exc).__name__,
                "partial_text": "".join(self.text_parts),
                "chunks": self.chunk_count,
                "stream": True,
            },
            latency_ms=(time.perf_counter() - self.t0) * 1000.0,
            status="error",
        )
        self.guard.observe_span(span)


class _SyncStreamWrapper:
    """Transparent proxy around synchronous LLM stream iterators."""

    def __init__(self, stream: Any, acc: _StreamAccumulator) -> None:
        self._stream = stream
        self._iterator = iter(stream)
        self._acc = acc

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        try:
            chunk = next(self._iterator)
        except StopIteration:
            self._acc.finalize_ok()
            raise
        except Exception as exc:
            self._acc.finalize_error(exc)
            raise
        self._acc.observe_chunk(chunk)
        return chunk

    def close(self) -> None:
        try:
            closer = getattr(self._stream, "close", None)
            if callable(closer):
                closer()
        finally:
            self._acc.finalize_ok()

    def __enter__(self) -> "_SyncStreamWrapper":
        enter = getattr(self._stream, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        exit_fn = getattr(self._stream, "__exit__", None)
        try:
            if callable(exit_fn):
                exit_fn(exc_type, exc_val, exc_tb)
        finally:
            if exc_val is not None:
                self._acc.finalize_error(exc_val)
            else:
                self._acc.finalize_ok()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _AsyncStreamWrapper:
    """Transparent proxy around asynchronous LLM stream iterators."""

    def __init__(self, stream: Any, acc: _StreamAccumulator) -> None:
        self._stream = stream
        self._iterator = stream.__aiter__()
        self._acc = acc

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        try:
            chunk = await self._iterator.__anext__()
        except StopAsyncIteration:
            self._acc.finalize_ok()
            raise
        except Exception as exc:
            self._acc.finalize_error(exc)
            raise
        self._acc.observe_chunk(chunk)
        return chunk

    async def aclose(self) -> None:
        try:
            closer = getattr(self._stream, "aclose", None) or getattr(self._stream, "close", None)
            if callable(closer):
                res = closer()
                if inspect.isawaitable(res):
                    await res
        finally:
            self._acc.finalize_ok()

    async def __aenter__(self) -> "_AsyncStreamWrapper":
        enter = getattr(self._stream, "__aenter__", None)
        if callable(enter):
            res = enter()
            if inspect.isawaitable(res):
                await res
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        exit_fn = getattr(self._stream, "__aexit__", None)
        try:
            if callable(exit_fn):
                res = exit_fn(exc_type, exc_val, exc_tb)
                if inspect.isawaitable(res):
                    await res
        finally:
            if exc_val is not None:
                self._acc.finalize_error(exc_val)
            else:
                self._acc.finalize_ok()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _replay_stream_chunks(replayed: Dict[str, Any]) -> Iterator[Any]:
    """Emit synthetic OpenAI/Anthropic-shaped stream chunks from a replayed cassette span."""
    text = str(replayed.get("text") or "")
    usage = replayed.get("usage")
    yield _ReplayNode(
        choices=[_ReplayNode(index=0, delta=_ReplayNode(role="assistant", content=text))],
        delta=_ReplayNode(text=text),
        usage=_reconstruct_replay_object(usage) if isinstance(usage, Mapping) else None,
    )


async def _async_replay_stream_chunks(replayed: Dict[str, Any]) -> AsyncIterator[Any]:
    """Emit async synthetic stream chunks from a replayed cassette span."""
    for chunk in _replay_stream_chunks(replayed):
        yield chunk


def _wrap_llm_create(
    orig_create: Callable[..., Any],
    *,
    provider_label: str,
    recorder: FlightRecorder,
    guard: TrajectoryCircuitBreaker,
    replayer: Optional[CassetteReplayer],
    model_pricing: Optional[Mapping[str, Tuple[float, float]]],
    estimated_cost_usd: float,
) -> Callable[..., Any]:
    """Build a guarded sync/async `create(...)` method for OpenAI or Anthropic clients."""

    def _prepare(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        payload = _to_plain_dict(kwargs)
        if args:
            payload["_args"] = [_to_plain_value(a) for a in args]
        model = str(payload.get("model") or "unknown-model")
        actor = f"{provider_label}.{model}"
        return actor, model, payload

    def _finalize(
        actor: str,
        model: str,
        input_payload: Dict[str, Any],
        response: Any,
        elapsed_ms: float,
    ) -> Any:
        out_dict = _to_plain_dict(response)
        prompt_tokens, completion_tokens, explicit_cost = _extract_usage_tokens(out_dict)
        resolved_cost = (
            explicit_cost
            if explicit_cost is not None
            else _estimate_cost_usd(
                model,
                prompt_tokens,
                completion_tokens,
                model_pricing=model_pricing,
            )
        )
        span = recorder.record(
            kind="llm_turn",
            actor=actor,
            input_payload=input_payload,
            output_payload=out_dict,
            latency_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=resolved_cost,
            status="ok",
        )
        guard.observe_span(span)
        return response

    def _record_error(actor: str, input_payload: Dict[str, Any], exc: Exception, elapsed_ms: float) -> None:
        span = recorder.record(
            kind="llm_turn",
            actor=actor,
            input_payload=input_payload,
            output_payload={"error": str(exc), "error_type": type(exc).__name__},
            latency_ms=elapsed_ms,
            status="error",
        )
        guard.observe_span(span)

    if inspect.iscoroutinefunction(orig_create):

        @functools.wraps(orig_create)
        async def _async_create(*args: Any, **kwargs: Any) -> Any:
            actor, model, input_payload = _prepare(args, kwargs)
            wants_stream = bool(kwargs.get("stream"))
            if replayer is not None:
                replayed = replayer.replay_step("llm_turn", actor, input_payload)
                if wants_stream:
                    return _async_replay_stream_chunks(replayed)
                return _reconstruct_replay_object(replayed)

            t0 = time.perf_counter()
            reservation = guard.reserve_budget(estimated_cost_usd)
            try:
                response = await orig_create(*args, **kwargs)
            except Exception as exc:
                reservation.release()
                _record_error(actor, input_payload, exc, (time.perf_counter() - t0) * 1000.0)
                raise

            if wants_stream or hasattr(response, "__aiter__"):
                acc = _StreamAccumulator(
                    actor=actor,
                    model=model,
                    input_payload=input_payload,
                    recorder=recorder,
                    guard=guard,
                    reservation=reservation,
                    model_pricing=model_pricing,
                    t0=t0,
                )
                return _AsyncStreamWrapper(response, acc)

            out_dict = _to_plain_dict(response)
            pt, ct, ec = _extract_usage_tokens(out_dict)
            actual_cost = ec if ec is not None else _estimate_cost_usd(model, pt, ct, model_pricing=model_pricing)
            reservation.commit(actual_cost)
            return _finalize(actor, model, input_payload, response, (time.perf_counter() - t0) * 1000.0)

        return _async_create

    @functools.wraps(orig_create)
    def _sync_create(*args: Any, **kwargs: Any) -> Any:
        actor, model, input_payload = _prepare(args, kwargs)
        wants_stream = bool(kwargs.get("stream"))
        if replayer is not None:
            replayed = replayer.replay_step("llm_turn", actor, input_payload)
            if wants_stream:
                return _replay_stream_chunks(replayed)
            return _reconstruct_replay_object(replayed)

        t0 = time.perf_counter()
        reservation = guard.reserve_budget(estimated_cost_usd)
        try:
            response = orig_create(*args, **kwargs)
        except Exception as exc:
            reservation.release()
            _record_error(actor, input_payload, exc, (time.perf_counter() - t0) * 1000.0)
            raise

        if wants_stream and hasattr(response, "__iter__") and not isinstance(response, (dict, bytes, str)):
            acc = _StreamAccumulator(
                actor=actor,
                model=model,
                input_payload=input_payload,
                recorder=recorder,
                guard=guard,
                reservation=reservation,
                model_pricing=model_pricing,
                t0=t0,
            )
            return _SyncStreamWrapper(response, acc)

        out_dict = _to_plain_dict(response)
        pt, ct, ec = _extract_usage_tokens(out_dict)
        actual_cost = ec if ec is not None else _estimate_cost_usd(model, pt, ct, model_pricing=model_pricing)
        reservation.commit(actual_cost)
        return _finalize(actor, model, input_payload, response, (time.perf_counter() - t0) * 1000.0)

    return _sync_create


def wrap_openai(
    client: Any,
    *,
    recorder: Optional[FlightRecorder] = None,
    guard: Optional[TrajectoryCircuitBreaker] = None,
    replayer: Optional[CassetteReplayer] = None,
    actor_prefix: str = "openai",
    model_pricing: Optional[Mapping[str, Tuple[float, float]]] = None,
    estimated_cost_usd: float = 0.0,
) -> Any:
    """
    1-line drop-in wrapper for `OpenAI`, `AsyncOpenAI`, OpenRouter, vLLM, or OpenAny clients.

    Intercepts `client.chat.completions.create(...)` (and `client.responses.create(...)`
    when available) with SHA-256 recording, circuit breaking, and offline cassette replay.
    """
    rec = recorder or FlightRecorder(agent_id=f"{actor_prefix}-client")
    breaker = guard or TrajectoryCircuitBreaker()
    overrides: Dict[str, Any] = {}

    if hasattr(client, "chat") and hasattr(client.chat, "completions") and hasattr(client.chat.completions, "create"):
        wrapped_create = _wrap_llm_create(
            client.chat.completions.create,
            provider_label=actor_prefix,
            recorder=rec,
            guard=breaker,
            replayer=replayer,
            model_pricing=model_pricing,
            estimated_cost_usd=estimated_cost_usd,
        )
        completions_proxy = _NamespaceProxy(client.chat.completions, create=wrapped_create)
        overrides["chat"] = _NamespaceProxy(client.chat, completions=completions_proxy)

    if hasattr(client, "responses") and hasattr(client.responses, "create"):
        wrapped_responses = _wrap_llm_create(
            client.responses.create,
            provider_label=actor_prefix,
            recorder=rec,
            guard=breaker,
            replayer=replayer,
            model_pricing=model_pricing,
            estimated_cost_usd=estimated_cost_usd,
        )
        overrides["responses"] = _NamespaceProxy(client.responses, create=wrapped_responses)

    if not overrides:
        raise TypeError("wrap_openai expected a client exposing `.chat.completions.create` or `.responses.create`.")

    proxy = _NamespaceProxy(client, **overrides)
    _attach_agentflight_handles(proxy, rec, breaker, replayer)
    return proxy


def wrap_anthropic(
    client: Any,
    *,
    recorder: Optional[FlightRecorder] = None,
    guard: Optional[TrajectoryCircuitBreaker] = None,
    replayer: Optional[CassetteReplayer] = None,
    actor_prefix: str = "anthropic",
    model_pricing: Optional[Mapping[str, Tuple[float, float]]] = None,
    estimated_cost_usd: float = 0.0,
) -> Any:
    """
    1-line drop-in wrapper for `Anthropic` and `AsyncAnthropic` SDK clients.

    Intercepts `client.messages.create(...)` with SHA-256 recording, cost/loop
    circuit breaking, and deterministic offline replay.
    """
    if not (hasattr(client, "messages") and hasattr(client.messages, "create")):
        raise TypeError("wrap_anthropic expected a client exposing `.messages.create`.")

    rec = recorder or FlightRecorder(agent_id=f"{actor_prefix}-client")
    breaker = guard or TrajectoryCircuitBreaker()
    wrapped_create = _wrap_llm_create(
        client.messages.create,
        provider_label=actor_prefix,
        recorder=rec,
        guard=breaker,
        replayer=replayer,
        model_pricing=model_pricing,
        estimated_cost_usd=estimated_cost_usd,
    )
    messages_proxy = _NamespaceProxy(client.messages, create=wrapped_create)
    proxy = _NamespaceProxy(client, messages=messages_proxy)
    _attach_agentflight_handles(proxy, rec, breaker, replayer)
    return proxy


class FlightCallbackHandler:
    """
    Duck-typed LangChain / LangGraph / OpenAny callback adapter with zero framework imports.

    Supports standard `on_llm_*` and `on_tool_*` lifecycle hooks as well as `.wrap_node(name, fn)`
    for graph nodes.
    """

    def __init__(
        self,
        recorder: Optional[FlightRecorder] = None,
        guard: Optional[TrajectoryCircuitBreaker] = None,
        *,
        agent_id: str = "callback-agent",
    ) -> None:
        self.recorder = recorder or FlightRecorder(agent_id=agent_id)
        self.guard = guard or TrajectoryCircuitBreaker()
        self._lock = threading.Lock()
        self._inflight: Dict[str, Tuple[str, str, Dict[str, Any], float]] = {}

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: Any,
        *,
        run_id: str = "default",
        **kwargs: Any,
    ) -> None:
        actor = str(serialized.get("name") or serialized.get("id") or "llm")
        with self._lock:
            self._inflight[str(run_id)] = (
                "llm_turn",
                actor,
                {"prompts": _to_plain_value(prompts), "kwargs": _to_plain_value(kwargs)},
                time.perf_counter(),
            )

    def on_llm_end(self, response: Any, *, run_id: str = "default", **kwargs: Any) -> None:
        with self._lock:
            kind, actor, input_payload, t0 = self._inflight.pop(
                str(run_id),
                ("llm_turn", "llm", {}, time.perf_counter()),
            )
        out_dict = _to_plain_dict(response)
        pt, ct, ec = _extract_usage_tokens(out_dict)
        cost = ec if ec is not None else 0.0
        span = self.recorder.record(
            kind=kind,  # type: ignore[arg-type]
            actor=actor,
            input_payload=input_payload,
            output_payload=out_dict,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=cost,
            status="ok",
        )
        self.guard.observe_span(span)

    def on_llm_error(self, error: BaseException, *, run_id: str = "default", **kwargs: Any) -> None:
        with self._lock:
            kind, actor, input_payload, t0 = self._inflight.pop(
                str(run_id),
                ("llm_turn", "llm", {}, time.perf_counter()),
            )
        span = self.recorder.record(
            kind=kind,  # type: ignore[arg-type]
            actor=actor,
            input_payload=input_payload,
            output_payload={"error": str(error), "error_type": type(error).__name__},
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            status="error",
        )
        self.guard.observe_span(span)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: Any,
        *,
        run_id: str = "default",
        **kwargs: Any,
    ) -> None:
        actor = str(serialized.get("name") or "tool")
        with self._lock:
            self._inflight[str(run_id)] = (
                "tool_call",
                actor,
                {"input": _to_plain_value(input_str), "kwargs": _to_plain_value(kwargs)},
                time.perf_counter(),
            )

    def on_tool_end(self, output: Any, *, run_id: str = "default", **kwargs: Any) -> None:
        with self._lock:
            kind, actor, input_payload, t0 = self._inflight.pop(
                str(run_id),
                ("tool_call", "tool", {}, time.perf_counter()),
            )
        span = self.recorder.record(
            kind=kind,  # type: ignore[arg-type]
            actor=actor,
            input_payload=input_payload,
            output_payload=_to_plain_dict(output),
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            status="ok",
        )
        self.guard.observe_span(span)

    def on_tool_error(self, error: BaseException, *, run_id: str = "default", **kwargs: Any) -> None:
        with self._lock:
            kind, actor, input_payload, t0 = self._inflight.pop(
                str(run_id),
                ("tool_call", "tool", {}, time.perf_counter()),
            )
        span = self.recorder.record(
            kind=kind,  # type: ignore[arg-type]
            actor=actor,
            input_payload=input_payload,
            output_payload={"error": str(error), "error_type": type(error).__name__},
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            status="error",
        )
        self.guard.observe_span(span)

    def wrap_node(self, node_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap any LangGraph / OpenAny node callable under this callback handler's recorder & guard."""
        return wrap_callable(
            fn,
            kind="state_checkpoint",
            actor=node_name,
            recorder=self.recorder,
            guard=self.guard,
        )
