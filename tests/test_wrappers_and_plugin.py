"""Unit & integration tests for v1.3.0 drop-in SDK wrappers and the auto-registered pytest11 plugin."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from agentflight import (
    CassetteReplayer,
    CircuitBreakerTripped,
    FlightCallbackHandler,
    FlightRecorder,
    TrajectoryCircuitBreaker,
    verify_cassette,
    wrap_anthropic,
    wrap_callable,
    wrap_openai,
)


def _fake_openai_response(text: str = "healthy", pt: int = 120, ct: int = 30) -> SimpleNamespace:
    return SimpleNamespace(
        id="chatcmpl-test",
        choices=[SimpleNamespace(index=0, message=SimpleNamespace(role="assistant", content=text))],
        usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct),
    )


def _fake_anthropic_response(text: str = "approved", it: int = 200, ot: int = 50) -> SimpleNamespace:
    return SimpleNamespace(
        id="msg-test",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=it, output_tokens=ot),
    )


def test_wrap_openai_records_and_replays(tmp_path: Path) -> None:
    calls: List[Dict[str, Any]] = []

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return _fake_openai_response(f"ok:{len(calls)}")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()), extra_attr="preserved")

    rec = FlightRecorder(agent_id="openai-test")
    client = wrap_openai(fake_client, recorder=rec)
    assert client.extra_attr == "preserved"

    resp1 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "status?"}],
    )
    assert resp1.choices[0].message.content == "ok:1"
    assert len(rec.spans) == 1
    assert rec.spans[0].actor == "openai.gpt-4o-mini"
    assert rec.spans[0].prompt_tokens == 120
    assert rec.spans[0].completion_tokens == 30
    assert rec.spans[0].cost_usd > 0
    assert verify_cassette(rec) is True

    cassette = tmp_path / "openai.flight.json"
    rec.save(cassette)

    # Replay mode: zero network/client calls & attribute access works identically
    replayer = CassetteReplayer(cassette)
    offline_client = wrap_openai(fake_client, replayer=replayer)
    before_calls = len(calls)
    replayed_resp = offline_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "status?"}],
    )
    assert len(calls) == before_calls
    assert replayed_resp.choices[0].message.content == "ok:1"
    assert replayed_resp.usage.prompt_tokens == 120


def test_wrap_openai_budget_block_and_loop_halt() -> None:
    invoked = 0

    class FakeCompletions:
        def create(self, **kwargs: Any) -> Any:
            nonlocal invoked
            invoked += 1
            return _fake_openai_response("hi")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    # 1. Pre-execution budget block prevents external call completely
    tight_guard = TrajectoryCircuitBreaker(max_cost_usd=0.01)
    blocked_client = wrap_openai(fake_client, guard=tight_guard, estimated_cost_usd=0.05)
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        blocked_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
    assert exc_info.value.reason == "cost_budget_exceeded"
    assert invoked == 0

    # 2. Identical loop guard halts on repeat
    loop_guard = TrajectoryCircuitBreaker(max_identical_repeats=2)
    loop_client = wrap_openai(fake_client, guard=loop_guard)
    loop_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "same"}])
    with pytest.raises(CircuitBreakerTripped) as loop_exc:
        loop_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "same"}])
    assert loop_exc.value.reason == "exact_call_loop"


def test_wrap_openai_async_and_responses_api() -> None:
    class FakeAsyncClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))
            self.responses = SimpleNamespace(create=self._resp_create)

        async def _chat_create(self, **kwargs: Any) -> Any:
            return _fake_openai_response("async-chat")

        async def _resp_create(self, **kwargs: Any) -> Any:
            return {"output_text": "async-responses", "usage": {"input_tokens": 50, "output_tokens": 25}}

    client = wrap_openai(FakeAsyncClient())

    async def _run() -> None:
        r1 = await client.chat.completions.create(model="gpt-4o-mini", messages=[])
        r2 = await client.responses.create(model="gpt-4.1-mini", input="ping")
        assert r1.choices[0].message.content == "async-chat"
        assert r2["output_text"] == "async-responses"

    asyncio.run(_run())
    assert len(client.agentflight_recorder.spans) == 2


def test_wrap_anthropic_records_error_and_replay() -> None:
    should_fail = False

    class FakeMessages:
        def create(self, **kwargs: Any) -> Any:
            if should_fail:
                raise RuntimeError("upstream 503")
            return _fake_anthropic_response("claude-ok")

    rec = FlightRecorder(agent_id="claude-agent")
    guard = TrajectoryCircuitBreaker(max_consecutive_errors=2)
    client = wrap_anthropic(SimpleNamespace(messages=FakeMessages()), recorder=rec, guard=guard)

    resp = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=128, messages=[])
    assert resp.content[0].text == "claude-ok"
    assert rec.spans[0].actor == "anthropic.claude-sonnet-4-20250514"
    assert rec.spans[0].prompt_tokens == 200
    assert rec.spans[0].completion_tokens == 50

    replayer = CassetteReplayer(rec)
    replayed = wrap_anthropic(SimpleNamespace(messages=FakeMessages()), replayer=replayer).messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=128,
        messages=[],
    )
    assert replayed.content[0].text == "claude-ok"

    should_fail = True
    with pytest.raises(RuntimeError, match="upstream 503"):
        client.messages.create(model="claude-sonnet-4-20250514", max_tokens=128, messages=[])
    assert rec.spans[-1].status == "error"
    assert guard.stats.consecutive_errors == 1


def test_wrap_callable_and_callback_handler() -> None:
    @wrap_callable
    def lookup_user(user_id: str) -> Dict[str, Any]:
        return {"user_id": user_id, "tier": "pro"}

    out = lookup_user(user_id="usr_42")
    assert out["tier"] == "pro"
    assert len(lookup_user.agentflight_recorder.spans) == 1

    handler = FlightCallbackHandler(agent_id="langgraph-sim")
    handler.on_llm_start({"name": "supervisor"}, ["Route ticket #9"], run_id="r1")
    handler.on_llm_end({"text": "call db_lookup", "usage": {"prompt_tokens": 40, "completion_tokens": 12}}, run_id="r1")
    handler.on_tool_start({"name": "db_lookup"}, "ticket_9", run_id="r2")
    handler.on_tool_end({"status": "open"}, run_id="r2")

    wrapped_node = handler.wrap_node("decision_node", lambda state: {"next": "done", **state})
    node_out = wrapped_node({"ticket": 9})
    assert node_out["next"] == "done"
    assert len(handler.recorder.spans) == 3
    assert verify_cassette(handler.recorder) is True


def test_auto_registered_pytest_fixtures_work(
    flight_recorder: FlightRecorder,
    flight_guard: TrajectoryCircuitBreaker,
    flight_session: Any,
) -> None:
    span = flight_recorder.record(
        kind="tool_call",
        actor="health_probe",
        input_payload={"env": "ci"},
        output_payload={"status": "ok"},
    )
    flight_guard.observe_span(span)
    assert len(flight_recorder.spans) == 1
    assert flight_guard.stats.steps_observed == 1

    stubbed = flight_session.stub("search", fallback_fn=lambda q: {"hits": [q]})
    assert stubbed(q="agentflight") == {"hits": ["agentflight"]}


@pytest.mark.flight_cassette(mode="record")
def test_flight_cassette_marker_records_and_verifies(flight_session: Any, tmp_path: Path) -> None:
    fn = flight_session.stub("calc", fallback_fn=lambda x: {"double": x * 2})
    assert fn(x=21) == {"double": 42}
    assert flight_session.cassette_path.parent == tmp_path
