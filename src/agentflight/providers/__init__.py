"""
agentflight.providers
=====================
Modular, Provider-Agnostic LLM & Tool Execution Abstractions for AgentFlight.

Enables seamless integration with model providers (such as OpenAny) while maintaining
strict black-box trajectory recording, deterministic replay, pre-execution cost
budget enforcement, and zero runtime vendor lock-in.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class BaseProvider(Protocol):
    """Protocol that all AgentFlight external providers implement."""

    name: str

    def is_configured(self) -> bool:
        """Return True if the provider has necessary credentials configured."""
        ...

    def get_models(self) -> List[Dict[str, Any]]:
        """Return list of supported models with pricing metadata."""
        ...


_PROVIDER_REGISTRY: Dict[str, Any] = {}


def register_provider(name: str, provider_cls: Any) -> None:
    """Register a provider implementation in the global registry."""
    _PROVIDER_REGISTRY[name.lower()] = provider_cls


def get_provider(name: str, **kwargs: Any) -> Any:
    """Instantiate a registered provider by name."""
    normalized = name.lower()
    if normalized not in _PROVIDER_REGISTRY:
        raise KeyError(
            f"Provider '{name}' is not registered. "
            f"Available providers: {sorted(_PROVIDER_REGISTRY.keys())}"
        )
    return _PROVIDER_REGISTRY[normalized](**kwargs)


def list_providers() -> List[str]:
    """Return list of all registered provider names."""
    return sorted(_PROVIDER_REGISTRY.keys())
