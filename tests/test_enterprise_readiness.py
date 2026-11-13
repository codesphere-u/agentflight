"""Tests for v1.4.0 enterprise production readiness:
- PII & secret redaction (`redact.py`, `FlightRecorder`, `CassetteReplayer`)
- `agentflight doctor` & CLI command matrix (`openany`, `ci`, `lint`, `post-mortem`, `fix`)
- Async/streaming wrappers, error callbacks & invalid-client guards (`wrappers.py`)
- Standalone HTTP & Vercel ASGI `/metrics`, `HEAD`, `X-Request-ID`, Upstash Redis rate limiter
- OpenAny HTTP retries & status error translation
"""

from __future__ import annotations

import asyncio
import http.client
import io
import json
import sys
import threading
import types
import urllib.error
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentflight import (
    CassetteReplayer,
    FlightCallbackHandler,
    FlightRecorder,
    TrajectoryCircuitBreaker,
    contains_sensitive_data,
    redact_cassette,
    redact_sensitive,
    verify_cassette,
    wrap_anthropic,
    wrap_callable,
    wrap_openai,
)
from agentflight.cli import main as cli_main
from agentflight.http_server import run_http_server
from agentflight.mcp_server import AgentFlightMCPServer
from agentflight.providers.openany import (
    OpenAnyAuthError,
    OpenAnyBudgetExceededError,
    OpenAnyConfig,
    OpenAnyError,
    OpenAnyInsufficientBalanceError,
    OpenAnyProvider,
    OpenAnyRateLimitError,
)
from agentflight.redact import REDACTED, redact_text

# ---------------------------------------------------------------------------
# 1. PII / Secret Redaction & Key-Rotated Deterministic Replay
# ---------------------------------------------------------------------------


def test_redact_text_and_nested_payloads_preserve_metrics() -> None:
    sample = (
        "auth=Bearer super_secret_bearer_token "
        "openai=sk-proj-abcdefghijklmnop1234 "
        "ant=sk-ant-api03-secretvalue12345 "
        "oa=oa_live_token_987654321 "
        "gh=ghp_1234567890abcdefghij "
        "aws=AKIAIOSFODNN7EXAMPLE "
        "jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U "
        "url=https://admin:hunter2@db.internal:5432/prod"
    )
    scrubbed = redact_text(sample)
    for leaked in (
        "super_secret_bearer_token",
        "sk-proj-abcdefghijklmnop1234",
        "sk-ant-api03-secretvalue12345",
        "oa_live_token_987654321",
        "ghp_1234567890abcdefghij",
        "AKIAIOSFODNN7EXAMPLE",
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        "admin:hunter2",
    ):
        assert leaked not in scrubbed
    assert "https://[REDACTED]@db.internal:5432/prod" in scrubbed

    nested = {
        "api_key": "raw-secret",
        "author": "Ada Lovelace",  # Must NOT be false-positive redacted as "auth"
        "prompt_tokens": 120,
        "completion_tokens": 45,
        "credentials": {"access_token": "tok-123", "scope": "read"},
        "schema": {"type": "object", "properties": {"api_key": {"type": "string"}}},
        "items": ("one", "sk-proj-abcdefghijklmnop1234"),
    }
    assert contains_sensitive_data(nested) is True
    clean = redact_sensitive(nested)
    assert clean["api_key"] == REDACTED
    assert clean["author"] == "Ada Lovelace"
    assert clean["prompt_tokens"] == 120
    assert clean["completion_tokens"] == 45
    assert clean["credentials"] == {"access_token": REDACTED, "scope": "read"}
    assert clean["schema"]["properties"]["api_key"] == {"type": "string"}
    assert clean["items"] == ("one", REDACTED)
    assert contains_sensitive_data({"author": "Ada", "prompt_tokens": 5}) is False


def test_flight_recorder_auto_redacts_and_replays_across_rotated_keys(tmp_path: Path) -> None:
    cassette_path = tmp_path / "secure.flight.json"
    rec = FlightRecorder(
        agent_id="sec-agent",
        metadata={"Authorization": "Bearer live-prod-token-999", "env": "prod"},
    )
    rec.record(
        "tool_call",
        "fetch_api",
        {"url": "https://user:pass@api.example.com", "api_key": "sk-old-secret-111111111111"},
        {"cookie": "session=xyz", "status": 200, "note": "used sk-old-secret-111111111111"},
    )
    rec.save(cassette_path)

    raw_text = cassette_path.read_text(encoding="utf-8")
    assert "sk-old-secret-111111111111" not in raw_text
    assert "live-prod-token-999" not in raw_text
    assert "user:pass" not in raw_text

    loaded = json.loads(cassette_path.read_text(encoding="utf-8"))
    verify_cassette(loaded)

    # Rotate credentials in CI/replay and ensure both strict and unordered replay still match
    for strict in (True, False):
        replayer = CassetteReplayer(cassette_path, strict_order=strict)
        out = replayer.replay_step(
            "tool_call",
            "fetch_api",
            {"url": "https://other:pw2@api.example.com", "api_key": "sk-new-secret-222222222222"},
        )
        assert out["status"] == 200
        assert out["cookie"] == REDACTED


def test_redact_cassette_rehashes_legacy_unredacted_cassette() -> None:
    rec = FlightRecorder(agent_id="legacy", redact_secrets=False)
    rec.record(
        "llm_turn",
        "gpt-4o",
        {"prompt": "hi", "api_key": "sk-legacy-unredacted-123456"},
        {"reply": "Bearer secret_out_token_99"},
    )
    raw = rec.to_cassette_dict()
    assert "sk-legacy-unredacted-123456" in json.dumps(raw)

    sanitized_no_rehash = redact_cassette(raw, rehash=False)
    assert "sk-legacy-unredacted-123456" not in json.dumps(sanitized_no_rehash)

    sanitized = redact_cassette(raw, rehash=True)
    assert "sk-legacy-unredacted-123456" not in json.dumps(sanitized)
    assert "secret_out_token_99" not in json.dumps(sanitized)
    verify_cassette(sanitized)


# ---------------------------------------------------------------------------
# 2. `agentflight doctor` & CLI Full Command Matrix
# ---------------------------------------------------------------------------


def test_cli_doctor_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["doctor"]) == 0
    out_text = capsys.readouterr().out
    assert "agentflight doctor" in out_text
    assert "[PASS]" in out_text

    assert cli_main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["healthy"] is True
    assert len(payload["checks"]) == 5
    assert all(c["ok"] is True for c in payload["checks"])


def test_cli_ci_lint_export_post_mortem_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    bad_schema = tmp_path / "bad_tools.json"
    bad_schema.write_text(
        json.dumps([{"name": "exec", "description": "run", "inputSchema": {"properties": {"cmd": {}}}}]),
        encoding="utf-8",
    )
    assert cli_main(["lint", "--schema-file", str(bad_schema), "--json"]) == 1
    lint_out = json.loads(capsys.readouterr().out)
    assert lint_out["error_count"] >= 1

    # Post-mortem report saved to file (under $1 budget -> INFO/0; over $1 -> HIGH/1 in ci gate)
    rec_ok = FlightRecorder("pm-agent")
    rec_ok.record("llm_turn", "gpt-4o", {"q": 1}, {"a": 2}, cost_usd=0.05)
    cassette_ok = tmp_path / "pm_ok.flight.json"
    rec_ok.save(cassette_ok)
    md_out = tmp_path / "incident.md"
    assert cli_main(["post-mortem", str(cassette_ok), "--output", str(md_out)]) == 0
    assert md_out.is_file()

    rec = FlightRecorder("pm-agent")
    rec.record("llm_turn", "gpt-4o", {"q": 1}, {"a": 2}, cost_usd=5.0)
    cassette = tmp_path / "pm.flight.json"
    rec.save(cassette)
    assert cli_main(["post-mortem", str(cassette), "--json"]) == 1

    # CI gate failure on smell & cost breach + GITHUB_STEP_SUMMARY
    gh_summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(gh_summary))
    rc_ci = cli_main([
        "ci",
        "--schema-file",
        str(bad_schema),
        "--cassette",
        str(cassette),
        "--max-cost",
        "1.0",
        "--fail-on-smell",
        "--github-summary",
    ])
    assert rc_ci == 1
    assert "AgentFlight CI" in gh_summary.read_text(encoding="utf-8")

    # Export OTel & fix --in-place
    otel_path = tmp_path / "trace.otel.json"
    assert cli_main(["export-otel", str(cassette), "--output", str(otel_path)]) == 0
    assert otel_path.is_file()
    assert cli_main(["fix", str(bad_schema), "--in-place"]) == 0
    fixed = json.loads(bad_schema.read_text(encoding="utf-8"))
    assert fixed[0]["inputSchema"]["type"] == "object"
    assert isinstance(fixed[0]["inputSchema"].get("required"), list)
    assert fixed[0]["inputSchema"]["properties"]["cmd"]["type"] == "string"


def test_cli_openany_commands_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import agentflight.providers.openany as openany_mod

    class FakeOpenAnyProvider:
        def __init__(self, config: Any = None) -> None:
            self.config = config

        def get_models(self) -> List[Dict[str, Any]]:
            return [
                {
                    "id": f"model-{i}",
                    "context_length": 128000,
                    "max_output_length": 4096,
                    "pricing": [{"prompt": "0.000001", "completion": "0.000002"}],
                    "input_modalities": ["text"],
                }
                for i in range(27)
            ]

        def lint_openany_tools(self) -> Any:
            from agentflight.linter import SHOWCASE_HARDENED_MCP_TOOLS, ToolSmellLinter
            return ToolSmellLinter().lint(SHOWCASE_HARDENED_MCP_TOOLS)

        def chat_completion(self, *, messages: Any, model: str, guard: Any, recorder: Any) -> Dict[str, Any]:
            if model == "over-budget":
                raise OpenAnyBudgetExceededError(
                    "cap reached",
                    step_index=1,
                    estimated_cost_usd=0.8,
                    current_spent_usd=0.0,
                    budget_limit_usd=0.5,
                )
            if model == "boom":
                raise RuntimeError("transient outage")
            if recorder is not None:
                recorder.record("llm_turn", model, {"messages": messages}, {"content": "hello"}, cost_usd=0.001)
            return {
                "choices": [{"message": {"content": "hello from mock"}}],
                "usage": {"total_tokens": 15, "prompt_tokens": 10, "completion_tokens": 5},
                "_agentflight": {"estimated_cost_usd": 0.001, "actual_cost_usd": 0.001, "latency_ms": 4.2, "partner_id": "agentflight"},
            }

    monkeypatch.setattr(openany_mod, "OpenAnyProvider", FakeOpenAnyProvider)

    assert cli_main(["openany", "models"]) == 0
    assert "more models" in capsys.readouterr().out
    assert cli_main(["openany", "models", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 27

    assert cli_main(["openany", "lint-tools"]) == 0
    assert cli_main(["openany", "lint-tools", "--json"]) == 0

    cassette_file = tmp_path / "openany_chat.flight.json"
    assert cli_main(["openany", "chat", "-p", "Hi", "--model", "MiniMax-M2.5", "--budget", "0.5", "--record", str(cassette_file)]) == 0
    assert cassette_file.is_file()
    assert cli_main(["openany", "chat", "-p", "Hi", "--model", "over-budget"]) == 2
    assert cli_main(["openany", "chat", "-p", "Hi", "--model", "boom"]) == 1
    assert cli_main(["openany", "replay", "--cassette", str(cassette_file)]) == 0
    assert cli_main(["openany"]) == 1


# ---------------------------------------------------------------------------
# 3. Async / Streaming / Error Branches in `wrappers.py`
# ---------------------------------------------------------------------------


def test_wrappers_async_streaming_errors_and_callbacks() -> None:
    rec = FlightRecorder("wrapper-edge")
    guard = TrajectoryCircuitBreaker(max_total_tokens=100_000, max_cost_usd=10.0)

    # 1. Invalid clients raise clean TypeError
    with pytest.raises(TypeError):
        wrap_openai(object(), recorder=rec)
    with pytest.raises(TypeError):
        wrap_anthropic(object(), recorder=rec)

    # 2. wrap_callable async success & error
    async def async_tool(x: int) -> Dict[str, Any]:
        if x < 0:
            raise ValueError("negative input")
        return {"double": x * 2}

    wrapped_async = wrap_callable(async_tool, recorder=rec, actor="math_tool")

    async def run_async_tests() -> None:
        assert await wrapped_async(x=7) == {"double": 14}
        with pytest.raises(ValueError, match="negative input"):
            await wrapped_async(x=-1)

    asyncio.run(run_async_tests())
    assert len(rec.spans) == 2
    assert rec.spans[1].status == "error"

    # 3. Sync OpenAI stream with tool_calls deltas + early close() + error callbacks
    class DeltaChunk:
        def __init__(self, idx: int, name: str | None = None, args: str | None = None, finish: str | None = None) -> None:
            fn = types.SimpleNamespace(name=name, arguments=args)
            tc = types.SimpleNamespace(index=idx, id="call_1", function=fn)
            delta = types.SimpleNamespace(content=None, tool_calls=[tc], role="assistant")
            self.choices = [types.SimpleNamespace(delta=delta, finish_reason=finish)]
            self.usage = None

    class FakeSyncStream:
        def __init__(self) -> None:
            self.closed = False
            self._items = iter([
                DeltaChunk(0, name="lookup", args='{"id":'),
                DeltaChunk(0, args=' 1}', finish="tool_calls"),
            ])

        def __iter__(self) -> "FakeSyncStream":
            return self

        def __next__(self) -> DeltaChunk:
            return next(self._items)

        def __enter__(self) -> "FakeSyncStream":
            return self

        def __exit__(self, *args: Any) -> None:
            self.close()

        def close(self) -> None:
            self.closed = True

    class FakeOpenAIClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs: Any) -> FakeSyncStream:
                    return FakeSyncStream()

    client = wrap_openai(FakeOpenAIClient(), recorder=rec, guard=guard)
    with client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}], stream=True) as st:
        collected = list(st)
    assert len(collected) == 2
    assert st._stream.closed is True
    last_span = rec.spans[-1]
    assert last_span.output_payload["tool_calls"][0]["function"]["name"] == "lookup"
    assert last_span.output_payload["tool_calls"][0]["function"]["arguments"] == '{"id": 1}'

    # 4. Async Anthropic stream with content_block_delta, message_delta & aclose()
    class FakeAsyncAnthropicStream:
        def __init__(self) -> None:
            self.closed = False
            self._items = [
                types.SimpleNamespace(type="message_start", message=types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=11))),
                types.SimpleNamespace(type="content_block_delta", delta=types.SimpleNamespace(type="text_delta", text="Async OK")),
                types.SimpleNamespace(type="message_delta", usage=types.SimpleNamespace(output_tokens=7)),
            ]

        def __aiter__(self) -> "FakeAsyncAnthropicStream":
            return self

        async def __anext__(self) -> Any:
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

        async def __aenter__(self) -> "FakeAsyncAnthropicStream":
            return self

        async def __aexit__(self, *args: Any) -> None:
            await self.aclose()

        async def aclose(self) -> None:
            self.closed = True

    class FakeAsyncAnthropicClient:
        class messages:
            @staticmethod
            async def create(**kwargs: Any) -> FakeAsyncAnthropicStream:
                return FakeAsyncAnthropicStream()

    a_ant = wrap_anthropic(FakeAsyncAnthropicClient(), recorder=rec, guard=guard)

    async def consume_ant() -> None:
        stream = await a_ant.messages.create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        async with stream:
            async for _ in stream:
                pass
        assert stream._stream.closed is True

    asyncio.run(consume_ant())
    assert rec.spans[-1].output_payload["text"] == "Async OK"

    # Async non-streaming OpenAI client + async stream replay + stream error recording
    class FakeAsyncOpenAI:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: Any) -> Any:
                    if kwargs.get("stream"):
                        async def err_gen() -> Any:
                            yield types.SimpleNamespace(
                                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="part"))],
                                usage=None,
                            )
                            raise RuntimeError("stream interrupted")

                        return err_gen()
                    return types.SimpleNamespace(
                        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="async hi"))],
                        usage=types.SimpleNamespace(prompt_tokens=6, completion_tokens=4),
                    )

    rec_async = FlightRecorder("async-replay")
    wrapped_async_oai = wrap_openai(FakeAsyncOpenAI(), recorder=rec_async)

    async def exercise_async_oai() -> None:
        r = await wrapped_async_oai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "ping"}],
        )
        assert r.choices[0].message.content == "async hi"

        # Mid-stream error commits finalize_error cleanly
        err_stream = await wrapped_async_oai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "boom"}],
            stream=True,
        )
        with pytest.raises(RuntimeError, match="stream interrupted"):
            async for _ in err_stream:
                pass

    asyncio.run(exercise_async_oai())
    assert rec_async.spans[-1].status == "error"
    assert rec_async.spans[-1].output_payload["partial_text"] == "part"

    # Record then deterministically replay async stream from recorded cassette
    class HealthyAsyncOpenAI:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: Any) -> Any:
                    async def ok_gen() -> Any:
                        yield types.SimpleNamespace(
                            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="Replayed async stream"))],
                            usage=None,
                        )

                    return ok_gen()

    healthy_rec = FlightRecorder("async-replay-stream")
    live_async = wrap_openai(HealthyAsyncOpenAI(), recorder=healthy_rec)

    async def record_then_replay() -> str:
        st_live = await live_async.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        _ = [c async for c in st_live]

        replayer = CassetteReplayer(healthy_rec)
        replayed_oai = wrap_openai(HealthyAsyncOpenAI(), replayer=replayer)
        st = await replayed_oai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        chunks = [c async for c in st]
        return "".join(c.choices[0].delta.content for c in chunks)

    assert "Replayed async stream" in asyncio.run(record_then_replay())

    # 5. FlightCallbackHandler error hooks
    cb = FlightCallbackHandler(recorder=rec, guard=guard)
    cb.on_llm_error(RuntimeError("rate limit"), run_id="r1")
    cb.on_tool_error(RuntimeError("timeout"), run_id="r2")
    assert rec.spans[-1].status == "error"


# ---------------------------------------------------------------------------
# 4. Standalone HTTP Server + Vercel ASGI Metrics / Upstash / X-Request-ID
# ---------------------------------------------------------------------------


def test_http_server_metrics_head_sse_and_error_paths() -> None:
    httpd = run_http_server(AgentFlightMCPServer(), host="127.0.0.1", port=0)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)

        conn.request("HEAD", "/health")
        r = conn.getresponse()
        r.read()
        assert r.status == 200
        assert r.getheader("X-Request-ID")

        conn.request("HEAD", "/nonexistent")
        r = conn.getresponse()
        r.read()
        assert r.status == 404

        conn.request("OPTIONS", "/mcp")
        r = conn.getresponse()
        r.read()
        assert r.status == 204
        assert "X-Request-ID" in (r.getheader("Access-Control-Expose-Headers") or "")

        conn.request("GET", "/unknown")
        r = conn.getresponse()
        assert r.status == 404
        r.read()

        # SSE stream returns initial endpoint event (read line-by-line since stream stays open)
        conn.request("GET", "/sse", headers={"X-Request-ID": "trace-sse-1"})
        r = conn.getresponse()
        assert r.status == 200
        assert "text/event-stream" in (r.getheader("Content-Type") or "")
        first_line = r.fp.readline().decode("utf-8")
        assert "event: endpoint" in first_line
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        # Notification-only batch -> 202
        batch_notif = json.dumps([{"jsonrpc": "2.0", "method": "notifications/initialized"}]).encode()
        conn.request("POST", "/mcp", body=batch_notif, headers={"Content-Type": "application/json", "Content-Length": str(len(batch_notif))})
        r = conn.getresponse()
        r.read()
        assert r.status == 202

        # Invalid Content-Length -> 400
        conn.request("POST", "/mcp", body=b"{}", headers={"Content-Length": "not-an-int"})
        r = conn.getresponse()
        r.read()
        assert r.status == 400

        # Prometheus + JSON metrics
        conn.request("GET", "/metrics")
        r = conn.getresponse()
        prom = r.read().decode("utf-8")
        assert r.status == 200
        assert "agentflight_requests_total" in prom
        assert "agentflight_mcp_calls_total" in prom

        conn.request("GET", "/metrics", headers={"Accept": "application/json"})
        r = conn.getresponse()
        snap = json.loads(r.read().decode("utf-8"))
        assert snap["requests_total"] >= 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_vercel_api_metrics_request_id_and_upstash_rate_limiter(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from api.index import _hits
    from api.index import app as vercel_app

    _hits.clear()
    client = TestClient(vercel_app)

    # Inbound X-Request-ID preserved + structured logging opt-in
    monkeypatch.setenv("AGENTFLIGHT_LOG_JSON", "1")
    r_health = client.get("/health", headers={"X-Request-ID": "req-prod-001"})
    assert r_health.status_code == 200
    assert r_health.headers["x-request-id"] == "req-prod-001"
    stderr_log = capsys.readouterr().err
    assert '"request_id":"req-prod-001"' in stderr_log
    monkeypatch.delenv("AGENTFLIGHT_LOG_JSON", raising=False)

    # Prometheus & JSON metrics endpoints
    r_head = client.head("/metrics")
    assert r_head.status_code == 200

    r_prom = client.get("/metrics")
    assert r_prom.status_code == 200
    assert "agentflight_requests_total" in r_prom.text

    r_json = client.get("/api/metrics", headers={"Accept": "application/json"})
    assert r_json.status_code == 200
    assert r_json.json()["runtime"] == "vercel-serverless"

    # Upstash Redis REST distributed rate limiter (allowed -> 429 -> fail-open fallback)
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://example.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "upstash-test-token")

    class FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=FakeResp(json.dumps([{"result": 1}, {"result": 1}]).encode())):
        ok_resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert ok_resp.status_code == 200

    with patch("urllib.request.urlopen", return_value=FakeResp(json.dumps([{"result": 999}, {"result": 1}]).encode())):
        limited = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers

    # Network error in Upstash falls back cleanly to local memory (allowed!)
    with patch("urllib.request.urlopen", side_effect=OSError("redis unreachable")):
        fallback_ok = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "ping"})
        assert fallback_ok.status_code == 200


# ---------------------------------------------------------------------------
# 5. OpenAny HTTP Status & Streaming Error Translation
# ---------------------------------------------------------------------------


def test_openany_http_and_stream_error_mapping() -> None:
    def make_provider(status: int, body: bytes = b"{}", headers: Dict[str, str] | None = None) -> OpenAnyProvider:
        cfg = OpenAnyConfig(api_key="oa_test", max_retries=0)
        return OpenAnyProvider(
            config=cfg,
            http_client=lambda req, timeout: (status, headers or {}, body),
        )

    with pytest.raises(OpenAnyAuthError):
        make_provider(401, b'{"error":{"message":"bad key"}}').get_models(force_refresh=True)
    with pytest.raises(OpenAnyInsufficientBalanceError):
        make_provider(402, b'{"error":{"message":"no credits"}}').get_models(force_refresh=True)
    with pytest.raises(OpenAnyRateLimitError):
        make_provider(429, b'{"error":{"message":"slow down"}}', {"retry-after": "1"}).get_models(force_refresh=True)
    with pytest.raises(OpenAnyError):
        make_provider(503, b"service unavailable").get_models(force_refresh=True)

    # Streaming HTTP error mapping via urllib.request.urlopen mock
    cfg = OpenAnyConfig(api_key="oa_stream", max_retries=0)
    prov = OpenAnyProvider(config=cfg)
    for code, exc_cls in (
        (401, OpenAnyAuthError),
        (402, OpenAnyInsufficientBalanceError),
        (429, OpenAnyRateLimitError),
        (500, OpenAnyError),
    ):
        err = urllib.error.HTTPError("https://api.openany.si/v1/chat/completions", code, "err", {}, io.BytesIO(b"fail"))
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(exc_cls):
                list(prov._stream_request("https://api.openany.si/v1/chat/completions", {}))

    # ToolSchemaOptimizer schema hardening + bounds + non-dict recovery + MCP resources/prompts
    from agentflight import ToolSchemaOptimizer

    raw_tools: List[Dict[str, Any]] = [
        {
            "name": "do",
            "description": "do",
            "inputSchema": {
                "properties": {
                    "limit": {"type": "integer", "description": ""},
                    "items": "non-dict-prop",
                    "filters": {"properties": {"tag": {}}},
                },
                "required": "invalid",
            },
        },
        {"name": "   ", "description": "run", "inputSchema": "invalid"},
    ]
    results = ToolSchemaOptimizer().optimize_tools(raw_tools)
    assert results[0].smells_resolved >= 1
    props = results[0].hardened_tool["inputSchema"]["properties"]
    assert props["limit"]["maximum"] >= 1
    assert props["items"]["type"] == "string"
    assert results[1].hardened_tool["name"] == "unnamed_tool"
    assert results[1].hardened_tool["inputSchema"]["type"] == "object"

    # Cover MCP resources/read & prompts/get & OpenAnyProvider edge helpers
    srv = AgentFlightMCPServer()
    res_list = srv.handle_request({"jsonrpc": "2.0", "id": 10, "method": "resources/list"})
    assert res_list is not None
    uri = res_list["result"]["resources"][0]["uri"]
    res_read = srv.handle_request({"jsonrpc": "2.0", "id": 11, "method": "resources/read", "params": {"uri": uri}})
    assert res_read is not None and "contents" in res_read["result"]
    prm_list = srv.handle_request({"jsonrpc": "2.0", "id": 12, "method": "prompts/list"})
    assert prm_list is not None
    pname = prm_list["result"]["prompts"][0]["name"]
    prm_get = srv.handle_request({"jsonrpc": "2.0", "id": 13, "method": "prompts/get", "params": {"name": pname, "arguments": {}}})
    assert prm_get is not None and "messages" in prm_get["result"]

    # Discover MCP tools with cursor + retry-then-succeed on 503 + call_mcp_tool loop guard
    attempts = {"n": 0}

    def flaky_transport(req: Any, timeout: float) -> tuple[int, dict[str, str], bytes]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return 503, {}, b'{"error":{"message":"busy"}}'
        body = json.loads(req.data.decode("utf-8"))
        if body.get("method") == "tools/list":
            return 200, {}, json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "t1"}]}}).encode()
        return 200, {}, json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}}).encode()

    retry_prov = OpenAnyProvider(
        config=OpenAnyConfig(api_key="oa_retry", max_retries=1, retry_backoff_factor=0.001),
        http_client=flaky_transport,
    )
    assert retry_prov.discover_mcp_tools(cursor="page2") == [{"name": "t1"}]
    assert attempts["n"] == 2

    mcp_guard = TrajectoryCircuitBreaker(max_identical_repeats=2)
    mcp_rec = FlightRecorder("oa-mcp")
    assert retry_prov.call_mcp_tool("t1", {"q": "ok"}, guard=mcp_guard, recorder=mcp_rec) == {"ok": True}
    from agentflight import CircuitBreakerTripped

    with pytest.raises(CircuitBreakerTripped):
        retry_prov.call_mcp_tool("t1", {"q": "ok"}, guard=mcp_guard, recorder=mcp_rec)
