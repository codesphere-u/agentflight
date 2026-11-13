"""Lazy pytest11 entry point shim that defers importing `agentflight` until fixture execution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

import pytest

if TYPE_CHECKING:  # pragma: no cover
    from agentflight.guard import TrajectoryCircuitBreaker
    from agentflight.recorder import FlightRecorder
    from agentflight.testing import FlightSession


def pytest_addoption(parser: Any) -> None:
    """Register AgentFlight CLI options for pytest without eagerly importing `agentflight`."""
    group = parser.getgroup("agentflight")
    group.addoption(
        "--flight-mode",
        action="store",
        default=None,
        choices=["auto", "record", "replay", "live"],
        help="Override AgentFlight cassette mode for `flight_session` (auto|record|replay|live).",
    )
    group.addoption(
        "--flight-dir",
        action="store",
        default=None,
        help="Base directory for auto-named `.flight.json` cassettes.",
    )


def pytest_configure(config: Any) -> None:
    """Register AgentFlight pytest markers without eagerly importing `agentflight`."""
    config.addinivalue_line(
        "markers",
        "flight_cassette(path=None, mode='auto'): Configure AgentFlight cassette recording/replay.",
    )
    config.addinivalue_line(
        "markers",
        "flight_guard(**kwargs): Configure `TrajectoryCircuitBreaker` parameters for `flight_guard`.",
    )


@pytest.fixture
def flight_recorder(request: Any) -> "FlightRecorder":
    """Provide an isolated `FlightRecorder` tagged with the current pytest node ID."""
    from agentflight.pytest_plugin import build_flight_recorder

    return build_flight_recorder(request)


@pytest.fixture
def flight_guard(request: Any) -> "TrajectoryCircuitBreaker":
    """Provide a fresh `TrajectoryCircuitBreaker` initialized per test function."""
    from agentflight.pytest_plugin import build_flight_guard

    return build_flight_guard(request)


@pytest.fixture
def flight_session(request: Any, tmp_path: Path) -> Iterator["FlightSession"]:
    """Provide a context-managed `FlightSession` wired to `@pytest.mark.flight_cassette`."""
    from agentflight.pytest_plugin import open_flight_session

    with open_flight_session(request, tmp_path) as session:
        yield session
