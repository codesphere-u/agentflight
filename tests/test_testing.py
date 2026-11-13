"""
tests/test_testing.py
=====================
Unit tests for `agentflight.testing` (@flight_test and FlightSession).
"""

from __future__ import annotations

from pathlib import Path

from agentflight.testing import FlightSession, flight_test


def test_flight_session_auto_record_then_replay(tmp_path: Path):
    cassette = tmp_path / "sample_session.cassette.json"

    # 1. First execution: file does not exist -> records
    with FlightSession(cassette, mode="auto", agent_id="agent-007") as session:
        assert session.is_recording
        stub = session.stub("get_weather", fallback_fn=lambda city: {"temp": 22, "city": city})
        res = stub(city="Berlin")
        assert res["temp"] == 22
        assert session.step_count == 1

    assert cassette.exists()

    # 2. Second execution: file exists -> auto replays
    with FlightSession(cassette, mode="auto") as session:
        assert session.is_replaying
        stub = session.stub("get_weather")
        res = stub(city="Berlin")
        assert res["temp"] == 22
        assert res["city"] == "Berlin"


def test_flight_test_decorator(tmp_path: Path):
    cassette = tmp_path / "decorator_test.cassette.json"

    # Record pass
    @flight_test(cassette)
    def test_run(flight):
        stub = flight.stub("multiply", fallback_fn=lambda a, b: {"result": a * b})
        out = stub(a=6, b=7)
        assert out["result"] == 42

    test_run()
    assert cassette.exists()

    # Replay pass
    @flight_test(cassette, mode="replay")
    def test_replay(flight):
        assert flight.is_replaying
        stub = flight.stub("multiply")
        out = stub(a=6, b=7)
        assert out["result"] == 42

    test_replay()


def test_flight_session_wrap_function(tmp_path: Path):
    cassette = tmp_path / "wrap_test.cassette.json"

    def calculate_tax(amount: float, rate: float = 0.1) -> dict:
        return {"tax": round(amount * rate, 2)}

    # Record
    with FlightSession(cassette, mode="record") as session:
        wrapped = session.wrap(calculate_tax)
        out = wrapped(amount=100.0, rate=0.08)
        assert out["tax"] == 8.0

    # Replay
    with FlightSession(cassette, mode="replay") as session:
        wrapped = session.wrap(calculate_tax)
        out = wrapped(amount=100.0, rate=0.08)
        assert out["tax"] == 8.0
