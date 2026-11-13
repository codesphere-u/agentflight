"""
Secret & PII Redaction Utilities for AgentFlight.

Zero-dependency stdlib scrubber that removes API keys, Bearer tokens, OAuth
credentials, and sensitive payload fields before trajectory spans are hashed,
persisted into `.flight.json` cassettes, or emitted in logs.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_EXACT = frozenset({
    "auth",
    "authorization",
    "proxy-authorization",
    "proxy_authorization",
    "cookie",
    "set-cookie",
    "set_cookie",
    "secret",
    "password",
    "passwd",
    "passphrase",
    "credential",
    "credentials",
    "x-api-key",
    "x_api_key",
})

_SENSITIVE_KEY_TERMS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "passphrase",
    "credential",
    "private_key",
    "signing_key",
    "encryption_key",
    "access_key",
    "bearer",
    "authorization",
    "auth_header",
    "auth_token",
    "access_token",
    "refresh_token",
    "id_token",
    "session_token",
    "csrf_token",
    "client_secret",
    "webhook_secret",
)

_SAFE_TOKEN_FIELDS = frozenset({
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "max_tokens",
    "reasoning_tokens",
    "cached_tokens",
    "input_tokens",
    "output_tokens",
    "token_count",
    "tokens",
    "tokenizer",
    "tokenize",
})

# Pre-compiled patterns for common API keys and credential formats.
_SECRET_VALUE_PATTERNS: Tuple[Tuple[re.Pattern[str], Any], ...] = (
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{6,}"), "Bearer " + REDACTED),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{10,}\b"), REDACTED),
    (re.compile(r"\bsk-proj-[A-Za-z0-9_\-]{10,}\b"), REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), REDACTED),
    (re.compile(r"\boa_[A-Za-z0-9_\-]{8,}\b"), REDACTED),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"), REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), REDACTED),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), REDACTED),
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        REDACTED,
    ),
    (
        re.compile(r"(https?://)([^/\s:@]+:[^/\s@]+)@"),
        r"\1" + REDACTED + "@",
    ),
)


def _is_sensitive_key(key: str) -> bool:
    k = str(key).strip().lower()
    if not k:
        return False
    if k in _SENSITIVE_KEY_EXACT:
        return True
    if k.endswith("_key_id") or k in _SAFE_TOKEN_FIELDS or k.endswith("_tokens"):
        return False
    if any(term in k for term in _SENSITIVE_KEY_TERMS):
        return True
    if "token" in k or k.endswith("_auth") or k.startswith("auth_"):
        return True
    return False


def redact_text(text: str, secrets: Optional[Sequence[str]] = None) -> str:
    """Scrub explicit secrets and well-known credential patterns from a string."""
    val = text
    if secrets:
        for sec in secrets:
            if sec and len(sec) >= 4 and sec in val:
                val = val.replace(sec, REDACTED)
    for pattern, repl in _SECRET_VALUE_PATTERNS:
        val = pattern.sub(repl, val)
    return val


def redact_sensitive(data: Any, secrets: Optional[Sequence[str]] = None) -> Any:
    """
    Recursively redact API keys, Authorization headers, credentials, and
    sensitive tokens from dictionaries, lists, tuples, and strings.
    """
    if isinstance(data, dict):
        redacted: Dict[str, Any] = {}
        for k, v in data.items():
            if _is_sensitive_key(str(k)):
                if isinstance(v, (dict, list, tuple)):
                    # Preserve structural containers (e.g., nested credential objects) while scrubbing leaves
                    redacted[k] = redact_sensitive(v, secrets)
                else:
                    redacted[k] = REDACTED
            else:
                redacted[k] = redact_sensitive(v, secrets)
        return redacted

    if isinstance(data, list):
        return [redact_sensitive(item, secrets) for item in data]

    if isinstance(data, tuple):
        return tuple(redact_sensitive(item, secrets) for item in data)

    if isinstance(data, str):
        return redact_text(data, secrets)

    return data


def contains_sensitive_data(data: Any, secrets: Optional[Sequence[str]] = None) -> bool:
    """Return True if redacting `data` modifies any field or string."""
    return bool(redact_sensitive(data, secrets) != data)


def redact_cassette(
    cassette: Dict[str, Any],
    secrets: Optional[Sequence[str]] = None,
    *,
    rehash: bool = True,
) -> Dict[str, Any]:
    """
    Return a copy of a cassette dictionary with secrets/credentials redacted across
    metadata and every span's input/output payloads, optionally recomputing the
    SHA-256 chain hashes so `verify_cassette()` continues to pass.
    """
    out: Dict[str, Any] = copy.deepcopy(cassette)
    if "metadata" in out and isinstance(out["metadata"], dict):
        out["metadata"] = redact_sensitive(out["metadata"], secrets)

    raw_spans = out.get("spans")
    if not isinstance(raw_spans, list):
        return out

    from .recorder import GENESIS_HASH, TrajectorySpan

    prev_hash = GENESIS_HASH
    new_spans: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_spans):
        if not isinstance(item, dict):
            new_spans.append(item)
            continue
        item_copy = copy.deepcopy(item)
        item_copy["input_payload"] = redact_sensitive(item_copy.get("input_payload", {}), secrets)
        item_copy["output_payload"] = redact_sensitive(item_copy.get("output_payload", {}), secrets)
        if rehash:
            span = TrajectorySpan(
                step_index=idx,
                kind=item_copy.get("kind", "tool_call"),
                actor=str(item_copy.get("actor", "")),
                input_payload=item_copy["input_payload"],
                output_payload=item_copy["output_payload"],
                latency_ms=float(item_copy.get("latency_ms", 0.0)),
                prompt_tokens=int(item_copy.get("prompt_tokens", 0)),
                completion_tokens=int(item_copy.get("completion_tokens", 0)),
                cost_usd=float(item_copy.get("cost_usd", 0.0)),
                status=item_copy.get("status", "ok"),
            ).with_computed_hashes(prev_hash)
            prev_hash = span.step_hash
            new_spans.append(span.to_dict())
        else:
            new_spans.append(item_copy)

    out["spans"] = new_spans
    if rehash:
        out["head_hash"] = prev_hash
    return out
