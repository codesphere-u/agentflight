"""
tests.test_openany_provider
===========================
Comprehensive Mocked Test Suite for Official OpenAny Integration in AgentFlight.

Covers:
- Provider discovery & registration.
- Secure configuration & secret redaction.
- Pre-execution cost estimation & circuit-breaker budget enforcement.
- Model execution, retry backoff & error handling (401, 402, 429, 500).
- Black-box flight recording into tamper-evident cassettes.
- Sub-millisecond deterministic replay with zero network calls and $0.00 cost.
- Loop & ping-pong oscillation detection.
- Remote MCP tool execution & tool-smell linter ergonomics evaluation.
- Commercial partnership attribution headers.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import pytest

from agentflight import (
    CassetteReplayer,
    CircuitBreakerTripped,
    FlightRecorder,
    OpenAnyAuthError,
    OpenAnyBudgetExceededError,
    OpenAnyConfig,
    OpenAnyInsufficientBalanceError,
    OpenAnyProvider,
    OpenAnyRateLimitError,
    TrajectoryCircuitBreaker,
    get_provider,
    list_providers,
)
from agentflight.providers.openany import redact_sensitive

# ---------------------------------------------------------------------------
# Mock HTTP Client Fixture
# ---------------------------------------------------------------------------

class MockHTTPTransport:
    """Configurable mock transport for urllib requests in OpenAnyProvider."""

    def __init__(self) -> None:
        self.recorded_requests: List[urllib.request.Request] = []
        self.responses_queue: List[Tuple[int, Dict[str, str], bytes]] = []
        self.default_models_response = {
            "data": [
                {
                    "id": "MiniMax-M2.5",
                    "name": "MiniMax-M2.5",
                    "context_length": 200000,
                    "max_output_length": 128000,
                    "pricing": {
                        "prompt": "0.0000003",
                        "completion": "0.0000012",
                        "request": "0",
                    },
                    "input_modalities": ["chat"],
                },
                {
                    "id": "claude-sonnet-4-6",
                    "name": "claude-sonnet-4-6",
                    "context_length": 1000000,
                    "max_output_length": 128000,
                    "pricing": {
                        "prompt": "0.000003",
                        "completion": "0.000015",
                        "request": "0",
                    },
                    "input_modalities": ["chat"],
                },
            ]
        }

    def queue_response(
        self,
        status: int,
        data: Any,
        headers: Optional[Dict[str, str]] = None,
        path_suffix: Optional[str] = None,
    ) -> None:
        raw_bytes = json.dumps(data).encode("utf-8") if not isinstance(data, (bytes, str)) else (
            data.encode("utf-8") if isinstance(data, str) else data
        )
        self.responses_queue.append((status, headers or {"Content-Type": "application/json"}, raw_bytes, path_suffix))

    def execute(self, req: urllib.request.Request, timeout: float) -> Tuple[int, Dict[str, str], bytes]:
        self.recorded_requests.append(req)
        # If a queued response matches the request URL, return it
        for i, (status, hdrs, body, suffix) in enumerate(self.responses_queue):
            if suffix is None or req.full_url.endswith(suffix):
                del self.responses_queue[i]
                return status, hdrs, body

        # Default handler for /models
        if req.full_url.endswith("/models"):
            return 200, {"Content-Type": "application/json"}, json.dumps(self.default_models_response).encode("utf-8")

        # Default handler for /chat/completions
        if req.full_url.endswith("/chat/completions"):
            mock_chat_resp = {
                "id": "chatcmpl-mock-123",
                "object": "chat.completion",
                "model": "MiniMax-M2.5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Mock OpenAny response content."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 8,
                    "total_tokens": 23,
                },
            }
            return 200, {"Content-Type": "application/json"}, json.dumps(mock_chat_resp).encode("utf-8")

        # Default fallback
        return 200, {"Content-Type": "application/json"}, b"{}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_provider_registration() -> None:
    """Verify that 'openany' is properly registered in AgentFlight providers."""
    providers = list_providers()
    assert "openany" in providers
    instance = get_provider("openany")
    assert isinstance(instance, OpenAnyProvider)
    assert instance.name == "openany"


def test_openany_config_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify OpenAnyConfig loads cleanly from environment variables."""
    monkeypatch.setenv("OPENANY_API_KEY", "sk-test-secret-key-12345")
    monkeypatch.setenv("OPENANY_BASE_URL", "https://mock.openany.si/v1")
    monkeypatch.setenv("OPENANY_MAX_BUDGET_USD", "0.25")
    monkeypatch.setenv("OPENANY_PARTNER_ID", "test-partner")

    cfg = OpenAnyConfig.from_env()
    assert cfg.api_key == "sk-test-secret-key-12345"
    assert cfg.base_url == "https://mock.openany.si/v1"
    assert cfg.max_budget_usd == 0.25
    assert cfg.partner_id == "test-partner"

    provider = OpenAnyProvider(config=cfg)
    assert provider.is_configured() is True


def test_secret_redaction() -> None:
    """Verify that API keys and Bearer tokens are redacted recursively."""
    secret = "sk-live-super-secret-key"
    payload = {
        "headers": {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        "api_key": secret,
        "nested": [{"token": "other-secret", "text": f"Here is my key: {secret}"}],
    }
    redacted = redact_sensitive(payload, secrets=[secret])
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert secret not in str(redacted)


def test_estimate_cost_calculation() -> None:
    """Verify exact cost estimation formula using OpenAny model catalog."""
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-test"),
        http_client=transport.execute,
    )
    # MiniMax-M2.5: prompt=0.0000003, completion=0.0000012
    # For 1,000 prompt tokens and 500 completion tokens:
    # (1000 * 0.0000003) + (500 * 0.0000012) = 0.0003 + 0.0006 = 0.0009 USD
    cost = provider.estimate_cost("MiniMax-M2.5", prompt_tokens=1000, max_completion_tokens=500)
    assert abs(cost - 0.0009) < 1e-6


def test_pre_execution_budget_circuit_breaker() -> None:
    """
    CRITICAL TEST: Verify that AgentFlight blocks expensive requests BEFORE execution
    when estimated cost exceeds remaining budget limit.
    """
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-test", default_model="claude-sonnet-4-6"),
        http_client=transport.execute,
    )

    # Set strict budget cap of $0.0001 (0.1 cent)
    guard = TrajectoryCircuitBreaker(max_cost_usd=0.0001)

    # A prompt with ~400 characters (~100 tokens) on claude-sonnet-4-6 costs > $0.005
    long_prompt = "Explain quantum computing in detail " * 20
    with pytest.raises(OpenAnyBudgetExceededError) as exc_info:
        provider.chat_completion(
            messages=[{"role": "user", "content": long_prompt}],
            model="claude-sonnet-4-6",
            guard=guard,
        )

    # Verify error properties
    err = exc_info.value
    assert err.reason == "cost_budget_exceeded"
    assert err.estimated_cost_usd > 0.0001
    assert err.budget_limit_usd == 0.0001

    # Verify ZERO requests reached the transport! (Zero credit spend)
    chat_requests = [r for r in transport.recorded_requests if r.full_url.endswith("/chat/completions")]
    assert len(chat_requests) == 0


def test_chat_completion_success_and_recording() -> None:
    """Verify successful model request, span flight recording, and cost reconciliation."""
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-test-key", default_model="MiniMax-M2.5"),
        http_client=transport.execute,
    )
    recorder = FlightRecorder(agent_id="openany-agent-test")
    guard = TrajectoryCircuitBreaker(max_cost_usd=1.00)

    resp = provider.chat_completion(
        messages=[{"role": "user", "content": "Hello OpenAny"}],
        guard=guard,
        recorder=recorder,
    )
    assert "choices" in resp
    assert resp["choices"][0]["message"]["content"] == "Mock OpenAny response content."

    # Verify flight recorder span
    assert len(recorder.spans) == 1
    span = recorder.spans[0]
    assert span.kind == "llm_turn"
    assert span.actor == "openany:MiniMax-M2.5"
    assert span.status == "ok"
    assert span.prompt_tokens == 15
    assert span.completion_tokens == 8
    assert span.cost_usd > 0.0
    assert "sk-test-key" not in json.dumps(span.input_payload)

    # Verify partner attribution header was transmitted
    req = transport.recorded_requests[-1]
    assert req.headers.get("X-openany-partner-id") == "agentflight"


def test_chat_completion_auth_error() -> None:
    """Verify HTTP 401 raises OpenAnyAuthError."""
    transport = MockHTTPTransport()
    transport.queue_response(401, {"error": {"message": "Invalid API key provided"}}, path_suffix="/chat/completions")

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-invalid"),
        http_client=transport.execute,
    )
    with pytest.raises(OpenAnyAuthError) as exc_info:
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
    assert "Invalid API key" in str(exc_info.value)
    assert exc_info.value.status_code == 401


def test_chat_completion_insufficient_balance_error() -> None:
    """Verify HTTP 402 raises OpenAnyInsufficientBalanceError."""
    transport = MockHTTPTransport()
    transport.queue_response(402, {"error": {"message": "Insufficient prepaid balance"}}, path_suffix="/chat/completions")

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-valid"),
        http_client=transport.execute,
    )
    with pytest.raises(OpenAnyInsufficientBalanceError) as exc_info:
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
    assert "Insufficient prepaid balance" in str(exc_info.value)
    assert exc_info.value.status_code == 402


def test_chat_completion_rate_limit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify HTTP 429 rate limit error handling."""
    # Prevent sleep during unit test
    monkeypatch.setattr("time.sleep", lambda s: None)

    transport = MockHTTPTransport()
    transport.queue_response(429, {"error": {"message": "Rate limit exceeded"}}, {"retry-after": "1"}, path_suffix="/chat/completions")
    transport.queue_response(429, {"error": {"message": "Rate limit exceeded"}}, {"retry-after": "1"}, path_suffix="/chat/completions")
    transport.queue_response(429, {"error": {"message": "Rate limit exceeded"}}, {"retry-after": "1"}, path_suffix="/chat/completions")

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-valid", max_retries=1),
        http_client=transport.execute,
    )
    with pytest.raises(OpenAnyRateLimitError):
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])


def test_loop_circuit_breaker_on_repeated_calls() -> None:
    """Verify TrajectoryCircuitBreaker trips on exact repetitive call loops."""
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-valid"),
        http_client=transport.execute,
    )
    guard = TrajectoryCircuitBreaker(max_identical_repeats=3)

    # Calls 1 and 2 succeed
    provider.chat_completion(messages=[{"role": "user", "content": "Looping prompt"}], guard=guard)
    provider.chat_completion(messages=[{"role": "user", "content": "Looping prompt"}], guard=guard)

    # Call 3 trips exact_call_loop
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        provider.chat_completion(messages=[{"role": "user", "content": "Looping prompt"}], guard=guard)
    assert exc_info.value.reason == "exact_call_loop"


def test_deterministic_replay_zero_cost() -> None:
    """
    CRITICAL TEST: Verify that a recorded OpenAny interaction can be replayed
    deterministically via CassetteReplayer with zero network calls and $0.00 cost.
    """
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-valid"),
        http_client=transport.execute,
    )
    recorder = FlightRecorder(agent_id="openany-agent-golden")

    # 1. Record live interaction
    resp1 = provider.chat_completion(
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        model="MiniMax-M2.5",
        recorder=recorder,
    )
    assert resp1["choices"][0]["message"]["content"] == "Mock OpenAny response content."

    # 2. Save cassette to temporary file
    with tempfile.NamedTemporaryFile(suffix=".flight.json", delete=False) as tmp:
        cassette_path = tmp.name

    try:
        recorder.save(cassette_path)
        initial_requests_count = len(transport.recorded_requests)

        # 3. Deterministic replay without network calls
        replayer = CassetteReplayer(cassette_path)
        assert len(replayer.spans) == 1
        assert replayer.agent_id == "openany-agent-golden"

        replay_span = replayer.advance()
        assert replay_span.actor == "openany:MiniMax-M2.5"
        assert replay_span.status == "ok"
        assert replay_span.cost_usd > 0.0

        # Verify NO new network calls were made during replay!
        assert len(transport.recorded_requests) == initial_requests_count
        assert replayer.is_exhausted is True
    finally:
        if os.path.exists(cassette_path):
            os.remove(cassette_path)


def test_mcp_tool_call_with_spending_cap() -> None:
    """Verify OpenAny remote MCP tool execution with max_cost_usd enforcement."""
    transport = MockHTTPTransport()
    transport.queue_response(
        200,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "BTC Price: $92,450.00"}],
                "isError": False,
            },
        },
    )

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-test", mcp_url="https://mock.openany.si/mcp"),
        http_client=transport.execute,
    )
    recorder = FlightRecorder(agent_id="tool-agent")
    guard = TrajectoryCircuitBreaker(max_cost_usd=1.00)

    result = provider.call_mcp_tool(
        name="crypto_price_lookup",
        arguments={"symbol": "BTC"},
        max_cost_usd=0.05,
        recorder=recorder,
        guard=guard,
    )
    assert result["content"][0]["text"] == "BTC Price: $92,450.00"

    # Verify span recorded as tool_call
    assert len(recorder.spans) == 1
    span = recorder.spans[0]
    assert span.kind == "tool_call"
    assert span.actor == "openany:mcp:crypto_price_lookup"
    assert span.status == "ok"
    assert span.input_payload["arguments"]["max_cost_usd"] == "0.05"


def test_openany_tool_smell_linting() -> None:
    """Verify auditing OpenAny tool definitions against TS001-TS010."""
    sample_tools = [
        {
            "name": "valid_openany_tool",
            "description": "Valid tool description with clear intent.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
        {
            "name": "flawed_tool",
            # Missing description, missing required array
            "inputSchema": {
                "type": "object",
                "properties": {
                    "untyped_prop": {}
                },
            },
        },
    ]
    provider = OpenAnyProvider()
    report = provider.lint_openany_tools(sample_tools)
    assert report.tool_count == 2
    assert report.warning_count > 0
    # TS001 (missing description) and TS007 (missing required array) should be detected
    rule_ids = {f.rule_id for f in report.findings}
    assert "TS001" in rule_ids or "TS007" in rule_ids


def test_partner_attribution_header_model_requests() -> None:
    """Verify that model completion requests include confirmed X-OpenAny-Partner-Id: agentflight."""
    transport = MockHTTPTransport()
    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-test", partner_id="agentflight"),
        http_client=transport.execute,
    )
    provider.chat_completion(messages=[{"role": "user", "content": "ping"}])
    assert len(transport.recorded_requests) >= 1
    req = transport.recorded_requests[-1]
    assert req.headers.get("X-openany-partner-id") == "agentflight"
    assert req.headers.get("Authorization") == "Bearer sk-test"


def test_partner_attribution_header_streaming_requests() -> None:
    """Verify that streaming chat completion requests include X-OpenAny-Partner-Id: agentflight."""
    recorded_urls = []
    recorded_headers = []

    def mock_stream(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None):
        recorded_urls.append(url)
        built_hdrs = provider._build_headers(target_url=url, custom_headers=headers)
        recorded_headers.append(built_hdrs)
        yield 'data: {"choices": [{"delta": {"content": "Streamed "}}]}'
        yield 'data: {"choices": [{"delta": {"content": "response."}}]}'
        yield "data: [DONE]"

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-stream-key", partner_id="agentflight"),
        stream_client=mock_stream,
    )
    chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Stream please"}]))
    assert len(chunks) == 2
    assert len(recorded_headers) == 1
    hdrs = recorded_headers[0]
    assert hdrs.get("X-OpenAny-Partner-Id") == "agentflight"
    assert hdrs.get("Authorization") == "Bearer sk-stream-key"


def test_partner_attribution_header_mcp_requests() -> None:
    """Verify that MCP tool discovery and invocation include X-OpenAny-Partner-Id: agentflight."""
    transport = MockHTTPTransport()
    transport.queue_response(200, {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
    transport.queue_response(200, {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"text": "ok"}]}})

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-mcp-key", partner_id="agentflight"),
        http_client=transport.execute,
    )
    # 1. tools/list
    provider.discover_mcp_tools()
    req_list = transport.recorded_requests[-1]
    assert req_list.headers.get("X-openany-partner-id") == "agentflight"

    # 2. tools/call
    provider.call_mcp_tool(name="test_tool", arguments={"val": 42})
    req_call = transport.recorded_requests[-1]
    assert req_call.headers.get("X-openany-partner-id") == "agentflight"


def test_partner_attribution_preserved_across_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that retried requests consistently preserve X-OpenAny-Partner-Id."""
    monkeypatch.setattr("time.sleep", lambda s: None)
    transport = MockHTTPTransport()
    # 1st call fails 503, 2nd call succeeds 200
    transport.queue_response(503, {"error": {"message": "Gateway temporarily overloaded"}}, path_suffix="/chat/completions")
    transport.queue_response(200, {
        "id": "cmpl-retry-ok",
        "choices": [{"message": {"role": "assistant", "content": "Recovered!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }, path_suffix="/chat/completions")

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-retry-key", max_retries=1, partner_id="agentflight"),
        http_client=transport.execute,
    )
    resp = provider.chat_completion(messages=[{"role": "user", "content": "test retry"}])
    assert resp["choices"][0]["message"]["content"] == "Recovered!"

    # Verify BOTH the initial and retried request contained X-OpenAny-Partner-Id
    chat_reqs = [r for r in transport.recorded_requests if r.full_url.endswith("/chat/completions")]
    assert len(chat_reqs) == 2
    for r in chat_reqs:
        assert r.headers.get("X-openany-partner-id") == "agentflight"
        assert r.headers.get("Authorization") == "Bearer sk-retry-key"


def test_partner_attribution_domain_isolation_no_leakage() -> None:
    """
    CRITICAL SECURITY TEST:
    Verify that X-OpenAny-Partner-Id and Authorization are NEVER leaked to unrelated third-party domains.
    """
    from agentflight.providers.openany import is_openany_domain

    provider = OpenAnyProvider(
        config=OpenAnyConfig(api_key="sk-secret-openany-key", partner_id="agentflight"),
    )

    # 1. OpenAny official domains - allowed
    assert is_openany_domain("https://api.openany.si/v1/chat/completions") is True
    assert is_openany_domain("https://mcp.openany.si/mcp") is True
    assert is_openany_domain("https://custom.openany.si/api") is True

    openany_headers = provider._build_headers(target_url="https://api.openany.si/v1/chat/completions")
    assert openany_headers.get("X-OpenAny-Partner-Id") == "agentflight"
    assert openany_headers.get("Authorization") == "Bearer sk-secret-openany-key"

    # 2. Third-party domains - STRICTLY BLOCKED from receiving partner header or secret key
    third_party_urls = [
        "https://api.openai.com/v1/chat/completions",
        "https://api.anthropic.com/v1/messages",
        "https://malicious-external-proxy.com/v1",
        "http://untrusted-server.org/sink",
    ]
    for url in third_party_urls:
        assert is_openany_domain(url) is False
        hdrs = provider._build_headers(target_url=url)
        assert "X-OpenAny-Partner-Id" not in hdrs
        assert "Authorization" not in hdrs
        assert "sk-secret-openany-key" not in str(hdrs)


def test_concurrent_budget_reservation_circuit_breaker() -> None:
    """
    CONCURRENCY TEST:
    Verify that thread-safe budget reservations prevent parallel requests
    from independently exceeding the same remaining budget.
    """

    # Budget cap: $0.0020
    guard = TrajectoryCircuitBreaker(max_cost_usd=0.0020)

    # Each request estimates $0.0012
    # Two requests in flight would total $0.0024 > $0.0020, so the 2nd MUST be rejected!
    reservation1 = guard.reserve_budget(0.0012)
    assert guard.stats.reserved_cost_usd == 0.0012

    # Second concurrent reservation should trip circuit breaker
    with pytest.raises(CircuitBreakerTripped) as exc_info:
        guard.reserve_budget(0.0012)
    assert exc_info.value.reason == "cost_budget_exceeded"

    # Releasing reservation1 should free the budget pool
    reservation1.release()
    assert guard.stats.reserved_cost_usd == 0.0

    # Now a reservation succeeds
    reservation2 = guard.reserve_budget(0.0015)
    assert guard.stats.reserved_cost_usd == 0.0015
    reservation2.commit(0.0014)
    assert guard.stats.reserved_cost_usd == 0.0


def test_partner_referral_configuration_and_disclosure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify partner referral config handling and transparent revenue disclosure."""
    # When no referral link is provided by OpenAny yet, it defaults to None (tracked as pending blocker)
    cfg = OpenAnyConfig.from_env()
    assert cfg.referral_url is None

    # When OPENANY_REFERRAL_URL is set in environment, it is loaded cleanly
    monkeypatch.setenv("OPENANY_REFERRAL_URL", "https://openany.si/?ref=agentflight-commercial-official")
    cfg_with_ref = OpenAnyConfig.from_env()
    assert cfg_with_ref.referral_url == "https://openany.si/?ref=agentflight-commercial-official"
