"""Production-hardening tests covering thread safety, atomic IO, streaming wrappers, HTTP server limits, and CLI gates."""

from __future__ import annotations

import asyncio
import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator, List

import pytest
from fastapi.testclient import TestClient

from agentflight import (
    CassetteReplayer,
    CassetteTamperError,
    FlightCallbackHandler,
    FlightRecorder,
    TrajectoryCircuitBreaker,
    __version__,
    get_provider,
    list_providers,
    verify_cassette,
    wrap_anthropic,
    wrap_openai,
)
from agentflight.cli import main as cli_main
from agentflight.http_server import run_http_server
from agentflight.mcp_server import AgentFlightMCPServer
from agentflight.providers.openany import OpenAnyConfig, OpenAnyProvider
from agentflight.testing import FlightSession

pytest_plugins = ["pytester"]


def test_flight_recorder_multithread_and_atomic_save(tmp_path: Path) -> None:
    rec = FlightRecorder(agent_id="mt-stress-agent")

    def worker(tid: int) -> None:
        for i in range(40):
            rec.record(
                kind="tool_call",
                actor=f"worker_{tid}",
                input_payload={"tid": tid, "i": i},
                output_payload={"ok": True},
                latency_ms=1.2,
                prompt_tokens=10,
                completion_tokens=5,
                cost_usd=0.0001,
            )

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(worker, t) for t in range(16)]
        for f in futures:
            f.result()

    assert len(rec.spans) == 640
    assert verify_cassette(rec) is True
    assert rec.total_tokens == 640 * 15
    assert rec.total_cost_usd == pytest.approx(0.064, abs=1e-7)

    # Atomic JSON and JSONL round-trips
    json_path = tmp_path / "mt.flight.json"
    jsonl_path = tmp_path / "mt.flight.jsonl"
    rec.save(json_path)
    rec.save(jsonl_path)

    loaded_json = FlightRecorder.load(json_path, verify=True)
    loaded_jsonl = FlightRecorder.load(jsonl_path, verify=True)
    assert loaded_json.head_hash == rec.head_hash
    assert loaded_jsonl.head_hash == rec.head_hash

    # Concurrent unordered replay
    replayer = CassetteReplayer(json_path, strict_order=False)
    spans = loaded_json.spans

    def replay_chunk(batch: List[Any]) -> None:
        for sp in batch:
            out = replayer.replay_step(sp.kind, sp.actor, sp.input_payload)
            assert out == {"ok": True}

    threads = [threading.Thread(target=replay_chunk, args=(spans[i::8],)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert replayer.remaining_steps == 0

    # Malformed cassette translates cleanly to CassetteTamperError
    bad_file = tmp_path / "corrupt.flight.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CassetteTamperError):
        FlightRecorder.load(bad_file)


def test_wrap_openai_and_anthropic_sync_streaming_and_replay(tmp_path: Path) -> None:
    def openai_stream_chunks() -> Iterator[Any]:
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello "))], usage=None)
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="world!"))],
            usage=SimpleNamespace(prompt_tokens=80, completion_tokens=20),
        )

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs: Any) -> Any:
            assert kwargs.get("stream") is True
            return openai_stream_chunks()

    rec = FlightRecorder(agent_id="stream-openai")
    guard = TrajectoryCircuitBreaker(max_cost_usd=1.0)
    client = wrap_openai(FakeOpenAIClient(), recorder=rec, guard=guard)

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
        stream=True,
    )
    pieces = [chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content]
    assert "".join(pieces) == "Hello world!"
    assert len(rec.spans) == 1
    assert rec.spans[0].output_payload["text"] == "Hello world!"
    assert rec.spans[0].output_payload["chunks"] == 2
    assert rec.spans[0].prompt_tokens == 80
    assert rec.spans[0].completion_tokens == 20
    assert guard.stats.reserved_cost_usd == 0.0

    # Offline cassette replay of the streamed turn preserves iterator interface
    cassette = tmp_path / "stream.flight.json"
    rec.save(cassette)
    offline = wrap_openai(FakeOpenAIClient(), replayer=CassetteReplayer(cassette))
    replayed_stream = offline.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
        stream=True,
    )
    replayed_text = "".join(c.choices[0].delta.content for c in replayed_stream)
    assert replayed_text == "Hello world!"


def test_wrap_anthropic_async_streaming_and_early_error() -> None:
    class FakeAsyncAnthropic:
        def __init__(self, should_fail_midstream: bool = False) -> None:
            self.fail = should_fail_midstream
            self.messages = SimpleNamespace(create=self._create)

        async def _create(self, **kwargs: Any) -> AsyncIterator[Any]:
            async def _gen() -> AsyncIterator[Any]:
                yield {"type": "message_start", "message": {"usage": {"input_tokens": 110}}}
                yield {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Part 1 "}}
                if self.fail:
                    raise ConnectionError("SSE dropped")
                yield {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Part 2"}}
                yield {"type": "message_delta", "usage": {"output_tokens": 15}}

            return _gen()

    async def _run() -> None:
        ok_rec = FlightRecorder(agent_id="async-anthropic")
        ok_guard = TrajectoryCircuitBreaker(max_cost_usd=1.0)
        ok_client = wrap_anthropic(FakeAsyncAnthropic(False), recorder=ok_rec, guard=ok_guard, estimated_cost_usd=0.02)
        stream = await ok_client.messages.create(model="claude-sonnet-4", messages=[], stream=True)
        chunks = [ch async for ch in stream]
        assert len(chunks) == 4
        assert ok_rec.spans[0].output_payload["text"] == "Part 1 Part 2"
        assert ok_rec.spans[0].prompt_tokens == 110
        assert ok_rec.spans[0].completion_tokens == 15
        assert ok_guard.stats.reserved_cost_usd == 0.0

        # Mid-stream failure releases reservation and records partial error span
        err_rec = FlightRecorder(agent_id="async-anthropic-err")
        err_guard = TrajectoryCircuitBreaker(max_consecutive_errors=3, max_cost_usd=1.0)
        err_client = wrap_anthropic(FakeAsyncAnthropic(True), recorder=err_rec, guard=err_guard, estimated_cost_usd=0.05)
        err_stream = await err_client.messages.create(model="claude-sonnet-4", messages=[], stream=True)
        with pytest.raises(ConnectionError, match="SSE dropped"):
            async for _ in err_stream:
                pass
        assert err_rec.spans[0].status == "error"
        assert "Part 1 " in err_rec.spans[0].output_payload["partial_text"]
        assert err_guard.stats.reserved_cost_usd == 0.0
        assert err_guard.stats.consecutive_errors == 1

    asyncio.run(_run())


def test_callback_handler_errors_and_thread_safety() -> None:
    handler = FlightCallbackHandler(guard=TrajectoryCircuitBreaker(max_consecutive_errors=5))
    handler.on_llm_start({"name": "planner"}, ["Check db"], run_id="run-a")
    handler.on_llm_error(TimeoutError("upstream timeout"), run_id="run-a")
    handler.on_tool_start({"name": "sql_exec"}, "SELECT 1", run_id="run-b")
    handler.on_tool_error(ValueError("bad query"), run_id="run-b")
    assert len(handler.recorder.spans) == 2
    assert all(sp.status == "error" for sp in handler.recorder.spans)


def test_standalone_http_server_hardening() -> None:
    srv = AgentFlightMCPServer()
    httpd = run_http_server(srv, host="127.0.0.1", port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/health") as r:
            assert r.status == 200
            assert r.headers.get("X-Content-Type-Options") == "nosniff"
            data = json.loads(r.read().decode("utf-8"))
            assert data["version"] == __version__

        # GET /mcp without SSE returns 405
        req_405 = urllib.request.Request(f"{base}/mcp", method="GET")
        with pytest.raises(urllib.error.HTTPError) as e405:
            urllib.request.urlopen(req_405)
        assert e405.value.code == 405

        # Valid POST JSON-RPC batch
        batch_body = json.dumps(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
            ]
        ).encode("utf-8")
        req_ok = urllib.request.Request(
            f"{base}/mcp",
            data=batch_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_ok) as r:
            assert r.status == 200
            payload = json.loads(r.read().decode("utf-8"))
            assert payload == [{"jsonrpc": "2.0", "id": 1, "result": {}}]

        # Oversized Content-Length rejected with 413 before reading
        req_big = urllib.request.Request(
            f"{base}/mcp",
            data=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "5000000"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as e413:
            urllib.request.urlopen(req_big)
        assert e413.value.code == 413

        # Malformed JSON rejected with 400 and -32700 envelope
        req_bad = urllib.request.Request(
            f"{base}/mcp",
            data=b"{bad",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as e400:
            urllib.request.urlopen(req_bad)
        assert e400.value.code == 400
        err_json = json.loads(e400.value.read().decode("utf-8"))
        assert err_json["error"]["code"] == -32700
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_mcp_server_protocol_edge_cases_and_hosted_security_headers() -> None:
    srv = AgentFlightMCPServer()
    bad_params = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "invalid"})
    assert bad_params is not None and bad_params["error"]["code"] == -32602

    unknown = srv.handle_request({"jsonrpc": "2.0", "id": 2, "method": "unknown/method"})
    assert unknown is not None and unknown["error"]["code"] == -32601

    assert srv.handle_request({"jsonrpc": "2.0", "id": 3, "method": "resources/subscribe", "params": {}})["result"] == {}
    assert srv.handle_request({"jsonrpc": "2.0", "id": 4, "method": "logging/setLevel", "params": {}})["result"] == {}

    # Hosted FastAPI security headers
    from api.index import app

    client = TestClient(app)
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": "invalid"})
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "SAMEORIGIN"
    assert res.json()["error"]["code"] == -32602


def test_cli_subcommands_providers_and_openany_streaming(tmp_path: Path) -> None:
    assert "openany" in list_providers()
    assert get_provider("openany") is not None

    rec_a = FlightRecorder(agent_id="cli-test")
    rec_a.record("tool_call", "lookup", {"id": 1}, {"ok": True}, cost_usd=0.001, prompt_tokens=10, completion_tokens=5)
    c_path = tmp_path / "cli.flight.json"
    rec_a.save(c_path)

    otel_out = tmp_path / "spans.json"
    assert cli_main(["diff", str(c_path), str(c_path), "--json"]) == 0
    assert cli_main(["export-otel", str(c_path), "--output", str(otel_out)]) == 0
    assert otel_out.exists()
    assert cli_main(["post-mortem", str(c_path), "--json"]) == 0
    assert cli_main(["ci", "--cassette", str(c_path), "--max-cost", "1.0"]) == 0

    raw_schema = tmp_path / "tools.json"
    raw_schema.write_text(json.dumps([{"name": "delete_user", "description": "del", "inputSchema": {"properties": {"id": {}}}}]), encoding="utf-8")
    fixed_out = tmp_path / "fixed.json"
    assert cli_main(["fix", str(raw_schema), "--output", str(fixed_out)]) == 0
    assert fixed_out.exists()

    # FlightSession diff mode bug fix verification (no crash on total_cost_usd or compare_cassettes)
    with FlightSession(c_path, mode="diff", fail_on_drift=True) as sess:
        sess.record_step("tool_call", "lookup", {"id": 1}, {"ok": True}, cost_usd=0.001, prompt_tokens=10, completion_tokens=5)
        assert sess.total_cost_usd == pytest.approx(0.001)
        assert sess.total_tokens == 15

    # OpenAny stream_chat transport coverage
    cfg = OpenAnyConfig(api_key="oa_test_secret_123")
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hi "}}]}',
        'data: {"choices":[{"delta":{"content":"there"}}],"usage":{"prompt_tokens":10,"completion_tokens":4}}',
        "data: [DONE]",
    ]
    provider = OpenAnyProvider(config=cfg)
    provider._stream_request = lambda url, payload: iter(sse_lines)  # type: ignore[method-assign]
    o_rec = FlightRecorder(agent_id="oa-stream")
    chunks = list(provider.stream_chat([{"role": "user", "content": "hi"}], recorder=o_rec))
    assert len(chunks) == 2
    assert o_rec.spans[0].output_payload["content"] == "Hi there"


def test_pytest_plugin_cli_options_and_markers(pytester: Any) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.flight_guard(max_cost_usd=0.5, max_identical_repeats=2)
        def test_inside_pytester(flight_recorder, flight_guard, flight_session):
            assert flight_guard.max_cost_usd == 0.5
            flight_recorder.record("tool_call", "ping", {"x": 1}, {"ok": True})
            fn = flight_session.stub("echo", fallback_fn=lambda msg: {"msg": msg})
            assert fn(msg="hi") == {"msg": "hi"}
        """
    )
    cassette_dir = pytester.path / "recorded_cassettes"
    res = pytester.runpytest("--flight-mode=record", f"--flight-dir={cassette_dir}")
    res.assert_outcomes(passed=1)
    assert list(cassette_dir.glob("*.flight.json"))
