"""
agentflight.providers.openany
=============================
Official OpenAny Provider Integration for AgentFlight.

Provides production-grade access to OpenAny's 168+ AI models and 3,200+ external APIs
with AgentFlight black-box flight recording, pre-execution cost circuit breaking,
loop & ping-pong guardrails, sub-millisecond deterministic replay, and MCP tool-smell
ergonomics linting.

Official OpenAny Specification:
- Model API Base: `https://api.openany.si/v1`
- Remote MCP Server: `https://mcp.openany.si/mcp`
- Catalog & Portal: `https://openany.si`
- Open-Source Gateway: `https://github.com/AlephantAI/AIephant-AI-Agent-Gateway`
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Sequence, Union

from ..guard import CircuitBreakerTripped, TrajectoryCircuitBreaker
from ..linter import ToolLintReport, ToolSmellLinter
from ..recorder import FlightRecorder, TrajectorySpan
from . import register_provider


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OpenAnyError(Exception):
    """Base exception for all OpenAny provider errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_payload = error_payload or {}


class OpenAnyAuthError(OpenAnyError):
    """Raised when authentication fails (HTTP 401/403 or invalid API key)."""


class OpenAnyInsufficientBalanceError(OpenAnyError):
    """Raised when OpenAny prepaid account balance is insufficient (HTTP 402)."""


class OpenAnyRateLimitError(OpenAnyError):
    """Raised when request is throttled by OpenAny rate limiter (HTTP 429)."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        error_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code=429, error_payload=error_payload)
        self.retry_after = retry_after


class OpenAnyBudgetExceededError(CircuitBreakerTripped, OpenAnyError):
    """
    Raised BEFORE execution when estimated cost would exceed configured budget limits.
    Inherits from both `CircuitBreakerTripped` and `OpenAnyError`.
    """

    def __init__(
        self,
        message: str,
        *,
        step_index: int,
        estimated_cost_usd: float,
        current_spent_usd: float,
        budget_limit_usd: float,
    ) -> None:
        evidence = {
            "estimated_cost_usd": estimated_cost_usd,
            "current_spent_usd": current_spent_usd,
            "budget_limit_usd": budget_limit_usd,
            "excess_usd": round((current_spent_usd + estimated_cost_usd) - budget_limit_usd, 6),
        }
        CircuitBreakerTripped.__init__(
            self,
            message,
            reason="cost_budget_exceeded",
            step_index=step_index,
            evidence=evidence,
        )
        self.estimated_cost_usd = estimated_cost_usd
        self.current_spent_usd = current_spent_usd
        self.budget_limit_usd = budget_limit_usd


# ---------------------------------------------------------------------------
# Configuration & Redaction Helpers
# ---------------------------------------------------------------------------

@dataclass
class OpenAnyConfig:
    """Configuration options for OpenAny provider."""

    api_key: Optional[str] = None
    base_url: str = "https://api.openany.si/v1"
    mcp_url: str = "https://mcp.openany.si/mcp"
    default_model: str = "MiniMax-M2.5"
    max_budget_usd: float = 0.50
    partner_id: str = "agentflight"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    retry_backoff_factor: float = 0.5

    @classmethod
    def from_env(cls) -> "OpenAnyConfig":
        """Instantiate configuration from environment variables."""
        return cls(
            api_key=os.environ.get("OPENANY_API_KEY"),
            base_url=os.environ.get("OPENANY_BASE_URL", "https://api.openany.si/v1").rstrip("/"),
            mcp_url=os.environ.get("OPENANY_MCP_URL", "https://mcp.openany.si/mcp"),
            default_model=os.environ.get("OPENANY_DEFAULT_MODEL", "MiniMax-M2.5"),
            max_budget_usd=float(os.environ.get("OPENANY_MAX_BUDGET_USD", "0.50")),
            partner_id=os.environ.get("OPENANY_PARTNER_ID", "agentflight"),
            timeout_seconds=float(os.environ.get("OPENANY_TIMEOUT_SECONDS", "30.0")),
            max_retries=int(os.environ.get("OPENANY_MAX_RETRIES", "2")),
        )


def redact_sensitive(data: Any, secrets: Optional[Sequence[str]] = None) -> Any:
    """
    Recursively redact API keys, Authorization headers, and sensitive tokens
    from dictionaries, lists, and strings before logging or recording in cassettes.
    """
    secret_set = {s for s in (secrets or []) if s and len(s) >= 4}

    if isinstance(data, dict):
        redacted: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ("key", "secret", "token", "auth", "credential", "password")):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive(v, secrets)
        return redacted

    if isinstance(data, list):
        return [redact_sensitive(item, secrets) for item in data]

    if isinstance(data, str):
        val = data
        for sec in secret_set:
            if sec in val:
                val = val.replace(sec, "[REDACTED]")
        # Redact generic Bearer patterns
        if "Bearer " in val:
            import re
            val = re.sub(r"Bearer\s+([A-Za-z0-9_\-\.]{6,})", "Bearer [REDACTED]", val)
        return val

    return data


# ---------------------------------------------------------------------------
# OpenAny Provider Class
# ---------------------------------------------------------------------------

class OpenAnyProvider:
    """
    Official OpenAny Provider for AgentFlight.

    Enables calling OpenAny AI models and remote MCP tools with:
    - Pre-execution cost estimation and circuit breaker budget enforcement.
    - Black-box flight recording into tamper-evident cassettes.
    - Zero-cost deterministic replay support.
    - Loop and ping-pong cycle detection.
    - Tool ergonomics analysis using AgentFlight's ToolSmellLinter.
    """

    name: str = "openany"

    def __init__(
        self,
        config: Optional[OpenAnyConfig] = None,
        *,
        http_client: Optional[Callable[[urllib.request.Request, float], Any]] = None,
    ) -> None:
        self.config = config or OpenAnyConfig.from_env()
        self._http_client = http_client or self._default_http_execute
        self._model_cache: Dict[str, Dict[str, Any]] = {}
        self._model_cache_timestamp: float = 0.0

    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self.config.api_key and self.config.api_key.strip())

    # -----------------------------------------------------------------------
    # HTTP Transport
    # -----------------------------------------------------------------------

    def _default_http_execute(self, request: urllib.request.Request, timeout: float) -> Tuple[int, Dict[str, str], bytes]:
        """Execute HTTP request using standard library urllib."""
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.getcode()
                headers = dict(response.headers.items())
                body = response.read()
                return status, headers, body
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items()) if e.headers else {}
            body = e.read() if hasattr(e, "read") else b""
            return e.code, headers, body
        except urllib.error.URLError as e:
            raise OpenAnyError(f"Network error connecting to OpenAny: {e.reason}") from e

    def _build_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers including authentication, streamable accept, and partnership attribution."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "agentflight/1.1.0 (partner=openany; https://github.com/codesphere-u/agentflight)",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.strip()}"
        if self.config.partner_id:
            headers["X-Partner-Id"] = self.config.partner_id
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _send_request(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send JSON HTTP request with retries and structured error translation."""
        req_headers = self._build_headers(headers)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None

        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            try:
                status, resp_headers, body = self._http_client(req, self.config.timeout_seconds)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_factor * (2**attempt))
                    continue
                raise OpenAnyError(f"OpenAny request failed after {attempt+1} attempts: {e}") from e

            # Parse JSON body
            try:
                data_resp = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                data_resp = {"raw": body.decode("utf-8", errors="replace")}

            if 200 <= status < 300:
                return data_resp

            # Error handling
            msg = data_resp.get("error", {}).get("message") if isinstance(data_resp.get("error"), dict) else str(data_resp)
            if not msg or msg == "{}":
                msg = f"HTTP {status}"

            if status in (401, 403):
                raise OpenAnyAuthError(f"OpenAny authentication failed ({status}): {msg}", status_code=status, error_payload=data_resp)
            if status == 402:
                raise OpenAnyInsufficientBalanceError(f"OpenAny balance insufficient ({status}): {msg}", status_code=status, error_payload=data_resp)
            if status == 429:
                retry_after_str = resp_headers.get("retry-after")
                retry_after = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else 2.0
                if attempt < self.config.max_retries:
                    time.sleep(retry_after)
                    continue
                raise OpenAnyRateLimitError(f"OpenAny rate limit exceeded: {msg}", retry_after=retry_after, error_payload=data_resp)

            # 5xx Server errors - retry
            if status >= 500 and attempt < self.config.max_retries:
                time.sleep(self.config.retry_backoff_factor * (2**attempt))
                continue

            raise OpenAnyError(f"OpenAny API error ({status}): {msg}", status_code=status, error_payload=data_resp)

        raise OpenAnyError(f"OpenAny request failed: {last_error}")

    # -----------------------------------------------------------------------
    # Catalog Discovery & Model Pricing
    # -----------------------------------------------------------------------

    def get_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch published model catalog from OpenAny `/v1/models` endpoint,
        including context lengths and real-time per-token prompt/completion pricing.
        """
        now = time.time()
        # Cache for 10 minutes unless forced
        if not force_refresh and self._model_cache and (now - self._model_cache_timestamp < 600):
            return list(self._model_cache.values())

        url = f"{self.config.base_url}/models"
        resp = self._send_request(url, method="GET")
        data = resp.get("data", [])

        self._model_cache.clear()
        for item in data:
            model_id = item.get("id")
            if model_id:
                self._model_cache[model_id] = item
        self._model_cache_timestamp = now
        return list(self._model_cache.values())

    def get_model_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata and pricing schema for a specific model ID."""
        if not self._model_cache:
            try:
                self.get_models()
            except Exception:
                pass
        return self._model_cache.get(model_id)

    def estimate_cost(
        self,
        model_id: str,
        prompt_tokens: int,
        max_completion_tokens: int = 512,
    ) -> float:
        """
        Calculate deterministic pre-execution estimated cost in USD based on
        OpenAny's published per-token pricing schedule.
        """
        meta = self.get_model_metadata(model_id)
        if not meta:
            # Fallback conservative default: $1.00 / 1M prompt, $3.00 / 1M completion
            return round((prompt_tokens * 0.000001) + (max_completion_tokens * 0.000003), 8)

        pricing = meta.get("pricing", {})
        if isinstance(pricing, list):
            # Tiered pricing - pick first matching range
            p_prompt = 0.000001
            p_comp = 0.000003
            for tier in pricing:
                r_start = tier.get("range_start", 0) or 0
                r_end = tier.get("range_end")
                if prompt_tokens >= r_start and (r_end is None or prompt_tokens <= r_end):
                    p_prompt = float(tier.get("prompt", "0.000001"))
                    p_comp = float(tier.get("completion", "0.000003"))
                    break
        else:
            p_prompt = float(pricing.get("prompt", "0") or 0.0)
            p_comp = float(pricing.get("completion", "0") or 0.0)
            p_req = float(pricing.get("request", "0") or 0.0)

        cost = (prompt_tokens * p_prompt) + (max_completion_tokens * p_comp)
        if "p_req" in locals():
            cost += p_req
        return round(max(cost, 0.0), 8)

    # -----------------------------------------------------------------------
    # Core AgentFlight Integration: Chat Completion with Budget Guard & Flight Recorder
    # -----------------------------------------------------------------------

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        guard: Optional[TrajectoryCircuitBreaker] = None,
        recorder: Optional[FlightRecorder] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an AI chat completion request through OpenAny with:
        1. Pre-execution estimated token & cost evaluation.
        2. Immediate circuit breaker trip if budget is exceeded BEFORE execution.
        3. Real-time loop & ping-pong detection via TrajectoryCircuitBreaker.
        4. Tamper-evident flight recording into AgentFlight cassettes.
        5. Reconciliation of estimated cost with final billed usage.
        """
        target_model = model or self.config.default_model

        # 1. Estimate prompt tokens (~4 chars per token heuristic)
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        est_prompt_tokens = max(1, total_chars // 4)
        est_max_comp_tokens = max_tokens if max_tokens is not None else 512
        est_cost_usd = self.estimate_cost(target_model, est_prompt_tokens, est_max_comp_tokens)

        # 2. Check Budget Circuit Breaker BEFORE dispatching paid call
        if guard is not None and guard.max_cost_usd is not None:
            projected_total = guard.stats.total_cost_usd + est_cost_usd
            if projected_total > guard.max_cost_usd:
                raise OpenAnyBudgetExceededError(
                    f"OpenAny pre-execution budget guard tripped: estimated call cost ${est_cost_usd:.6f} "
                    f"would push total spend to ${projected_total:.6f}, exceeding max limit ${guard.max_cost_usd:.2f}.",
                    step_index=guard.stats.steps_observed,
                    estimated_cost_usd=est_cost_usd,
                    current_spent_usd=guard.stats.total_cost_usd,
                    budget_limit_usd=guard.max_cost_usd,
                )

        # 3. Check Pre-Execution Loop Detection
        actor_name = f"openany:{target_model}"
        request_input = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "estimated_cost_usd": est_cost_usd,
        }
        if guard is not None:
            from ..recorder import canonical_hash
            sig = (actor_name, canonical_hash(request_input))
            n_rep = guard.max_identical_repeats
            if len(guard._history) >= (n_rep - 1):
                tail = guard._history[-(n_rep - 1):]
                if all(item == sig for item in tail):
                    guard._trip(
                        reason="exact_call_loop",
                        step_index=guard.stats.steps_observed,
                        message=(
                            f"Exact call loop detected at step {guard.stats.steps_observed}: model '{actor_name}' invoked "
                            f"{n_rep} times consecutively with identical arguments."
                        ),
                        evidence={
                            "actor": actor_name,
                            "repeats": n_rep,
                            "input_payload": request_input,
                        },
                    )

        # 4. Dispatch live HTTP call
        url = f"{self.config.base_url}/chat/completions"
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_body:
            payload.update(extra_body)

        start_time = time.perf_counter()
        status_flag = "ok"
        error_info: Optional[Dict[str, Any]] = None
        resp_data: Dict[str, Any] = {}

        try:
            resp_data = self._send_request(url, method="POST", payload=payload)
        except Exception as e:
            status_flag = "error"
            error_info = {"error": str(e), "type": type(e).__name__}
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            # Record failed turn in flight recorder if provided
            if recorder is not None:
                recorder.record(
                    kind="llm_turn",
                    actor=actor_name,
                    input_payload=redact_sensitive(request_input, [self.config.api_key or ""]),
                    output_payload=error_info,
                    latency_ms=latency_ms,
                    status="error",
                )
            if guard is not None:
                guard.observe(
                    actor=actor_name,
                    input_payload=request_input,
                    status="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    kind="llm_turn",
                )
            raise

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Extract actual tokens & compute billed cost
        usage = resp_data.get("usage", {})
        actual_prompt_tokens = usage.get("prompt_tokens", est_prompt_tokens)
        actual_comp_tokens = usage.get("completion_tokens", 0)
        actual_total_tokens = usage.get("total_tokens", actual_prompt_tokens + actual_comp_tokens)

        actual_cost_usd = self.estimate_cost(target_model, actual_prompt_tokens, actual_comp_tokens)

        # 6. Reconcile with circuit breaker
        if guard is not None:
            guard.observe(
                actor=actor_name,
                input_payload=request_input,
                status="ok",
                prompt_tokens=actual_prompt_tokens,
                completion_tokens=actual_comp_tokens,
                cost_usd=actual_cost_usd,
                kind="llm_turn",
            )

        # 7. Record span into tamper-evident FlightRecorder cassette
        output_payload = redact_sensitive(resp_data, [self.config.api_key or ""])
        output_payload["_agentflight"] = {
            "estimated_cost_usd": est_cost_usd,
            "actual_cost_usd": actual_cost_usd,
            "latency_ms": round(latency_ms, 2),
            "partner_id": self.config.partner_id,
        }

        if recorder is not None:
            recorder.record(
                kind="llm_turn",
                actor=actor_name,
                input_payload=redact_sensitive(request_input, [self.config.api_key or ""]),
                output_payload=output_payload,
                latency_ms=latency_ms,
                prompt_tokens=actual_prompt_tokens,
                completion_tokens=actual_comp_tokens,
                cost_usd=actual_cost_usd,
                status="ok",
            )

        return resp_data

    # -----------------------------------------------------------------------
    # Remote MCP Integration (Tools & Data APIs)
    # -----------------------------------------------------------------------

    def discover_mcp_tools(self, cursor: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query OpenAny's remote Streamable HTTP JSON-RPC 2.0 MCP server (`tools/list`)
        to discover executable data and tool APIs.
        """
        req_payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        if cursor:
            req_payload["params"]["cursor"] = cursor

        resp = self._send_request(self.config.mcp_url, method="POST", payload=req_payload)
        result = resp.get("result", {})
        return result.get("tools", [])

    def call_mcp_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        max_cost_usd: Optional[float] = None,
        guard: Optional[TrajectoryCircuitBreaker] = None,
        recorder: Optional[FlightRecorder] = None,
    ) -> Dict[str, Any]:
        """
        Execute an OpenAny external tool over remote MCP JSON-RPC 2.0 with
        circuit breaking, spending caps, and flight recording.
        """
        cap = max_cost_usd or self.config.max_budget_usd
        tool_args = dict(arguments)
        if "max_cost_usd" not in tool_args:
            tool_args["max_cost_usd"] = str(cap)

        actor_name = f"openany:mcp:{name}"
        input_payload = {"tool": name, "arguments": tool_args}

        # Guard check
        if guard is not None:
            from ..recorder import canonical_hash
            sig = (actor_name, canonical_hash(input_payload))
            n_rep = guard.max_identical_repeats
            if len(guard._history) >= (n_rep - 1):
                tail = guard._history[-(n_rep - 1):]
                if all(item == sig for item in tail):
                    guard._trip(
                        reason="exact_call_loop",
                        step_index=guard.stats.steps_observed,
                        message=(
                            f"Exact call loop detected at step {guard.stats.steps_observed}: tool '{actor_name}' invoked "
                            f"{n_rep} times consecutively with identical arguments."
                        ),
                        evidence={
                            "actor": actor_name,
                            "repeats": n_rep,
                            "input_payload": input_payload,
                        },
                    )

        req_payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": tool_args,
            },
        }

        start_time = time.perf_counter()
        try:
            resp = self._send_request(self.config.mcp_url, method="POST", payload=req_payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            result = resp.get("result", resp)
            is_error = resp.get("error") is not None or result.get("isError", False)
            status_flag = "error" if is_error else "ok"

            if recorder is not None:
                recorder.record(
                    kind="tool_call",
                    actor=actor_name,
                    input_payload=redact_sensitive(input_payload, [self.config.api_key or ""]),
                    output_payload=redact_sensitive(result, [self.config.api_key or ""]),
                    latency_ms=latency_ms,
                    status=status_flag,
                )

            if guard is not None:
                guard.observe(
                    actor=actor_name,
                    input_payload=input_payload,
                    status=status_flag,
                    kind="tool_call",
                )

            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if recorder is not None:
                recorder.record(
                    kind="tool_call",
                    actor=actor_name,
                    input_payload=redact_sensitive(input_payload, [self.config.api_key or ""]),
                    output_payload={"error": str(e)},
                    latency_ms=latency_ms,
                    status="error",
                )
            if guard is not None:
                guard.observe(
                    actor=actor_name,
                    input_payload=input_payload,
                    status="error",
                    kind="tool_call",
                )
            raise

    def lint_openany_tools(
        self,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ToolLintReport:
        """
        Audit OpenAny MCP tool schemas against AgentFlight's 10 ergonomics rules (TS001-TS010)
        and compute the Agent Ergonomics Score (0-100).
        """
        if tools is None:
            tools = self.discover_mcp_tools()
        linter = ToolSmellLinter()
        return linter.lint(tools)


# Register OpenAny provider in global registry
register_provider("openany", OpenAnyProvider)
