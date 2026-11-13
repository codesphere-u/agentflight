"""
agentflight.pytest_plugin
=========================
Auto-registered `pytest11` helpers for AgentFlight.

Provides ready-to-use fixtures (`flight_recorder`, `flight_guard`, `flight_session`)
and `@pytest.mark.flight_cassette(path, mode="auto")` integration whenever
`agentflight-mcp` is installed alongside `pytest`.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import pytest
except ImportError:  # pragma: no cover - pytest is only present in test environments
    pytest = None  # type: ignore[assignment]

from agentflight.guard import TrajectoryCircuitBreaker
from agentflight.recorder import FlightRecorder
from agentflight.testing import FlightSession, RecordMode


def _safe_cassette_stem(node_name: str) -> str:
    """Convert a pytest node name into a filesystem-safe cassette stem."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", node_name).strip("_") or "test_flight"


def pytest_addoption(parser: Any) -> None:
    """Register AgentFlight CLI options for pytest."""
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
    """Register AgentFlight pytest markers."""
    config.addinivalue_line(
        "markers",
        "flight_cassette(path=None, mode='auto'): Configure AgentFlight cassette recording/replay.",
    )
    config.addinivalue_line(
        "markers",
        "flight_guard(**kwargs): Configure `TrajectoryCircuitBreaker` parameters for `flight_guard`.",
    )


def build_flight_recorder(request: Any) -> FlightRecorder:
    """Construct an isolated `FlightRecorder` tagged with the current pytest node ID."""
    return FlightRecorder(agent_id=request.node.nodeid)


def build_flight_guard(request: Any) -> TrajectoryCircuitBreaker:
    """Construct a `TrajectoryCircuitBreaker` honoring `@pytest.mark.flight_guard`."""
    marker = request.node.get_closest_marker("flight_guard")
    kwargs = dict(marker.kwargs) if marker is not None else {}
    return TrajectoryCircuitBreaker(**kwargs)


@contextmanager
def open_flight_session(request: Any, tmp_path: Path) -> Iterator[FlightSession]:
    """Open a context-managed `FlightSession` wired to `@pytest.mark.flight_cassette`."""
    marker = request.node.get_closest_marker("flight_cassette")
    cli_mode = request.config.getoption("--flight-mode")
    cli_dir = request.config.getoption("--flight-dir")

    mode: RecordMode = cli_mode or "auto"
    cassette_path: Path

    if marker is not None:
        marker_path = marker.args[0] if marker.args else marker.kwargs.get("path")
        if cli_mode is None and "mode" in marker.kwargs:
            mode = marker.kwargs["mode"]
        if marker_path is not None:
            cassette_path = Path(marker_path)
        else:
            base_dir = Path(cli_dir) if cli_dir else tmp_path
            cassette_path = base_dir / f"{_safe_cassette_stem(request.node.name)}.flight.json"
    else:
        base_dir = Path(cli_dir) if cli_dir else tmp_path
        cassette_path = base_dir / f"{_safe_cassette_stem(request.node.name)}.flight.json"

    with FlightSession(
        cassette_path,
        mode=mode,
        agent_id=request.node.nodeid,
    ) as session:
        yield session


if pytest is not None:

    @pytest.fixture
    def flight_recorder(request: Any) -> FlightRecorder:
        """Provide an isolated `FlightRecorder` tagged with the current pytest node ID."""
        return build_flight_recorder(request)

    @pytest.fixture
    def flight_guard(request: Any) -> TrajectoryCircuitBreaker:
        """Provide a fresh `TrajectoryCircuitBreaker` initialized per test function."""
        return build_flight_guard(request)

    @pytest.fixture
    def flight_session(request: Any, tmp_path: Path) -> Iterator[FlightSession]:
        """Provide a context-managed `FlightSession` wired to `@pytest.mark.flight_cassette`."""
        with open_flight_session(request, tmp_path) as session:
            yield session
