"""
tests/test_post_mortem.py
=========================
Unit tests for `agentflight.post_mortem` (FlightPostMortemAnalyzer).
"""

from __future__ import annotations

from pathlib import Path
from agentflight.post_mortem import FlightPostMortemAnalyzer
from agentflight.recorder import FlightRecorder


def test_post_mortem_healthy_flight(tmp_path: Path):
    rec = FlightRecorder(agent_id="healthy-bot")
    rec.record("tool_call", "search", {"q": "python"}, {"items": ["3.12"]}, latency_ms=10.0, cost_usd=0.0001)
    rec.record("tool_call", "summarize", {"items": ["3.12"]}, {"summary": "Latest Python"}, latency_ms=15.0, cost_usd=0.0002)
    cassette = tmp_path / "healthy.cassette.json"
    rec.save(cassette)

    analyzer = FlightPostMortemAnalyzer()
    report = analyzer.analyze(cassette)

    assert report.severity == "CLEAN"
    assert report.root_cause == "HEALTHY_FLIGHT"
    assert report.is_hash_chain_valid is True
    assert report.total_steps == 2
    assert "CLEAN" in report.to_markdown()


def test_post_mortem_unhandled_tool_fault(tmp_path: Path):
    rec = FlightRecorder(agent_id="failing-bot")
    rec.record("tool_call", "auth", {"user": "alice"}, {"status": "authorized"}, latency_ms=5.0)
    rec.record("tool_call", "delete_database", {"db": "prod"}, {"error": "Unauthorized Access"}, latency_ms=25.0, status="error")
    cassette = tmp_path / "fault.cassette.json"
    rec.save(cassette)

    analyzer = FlightPostMortemAnalyzer()
    report = analyzer.analyze(cassette)

    assert report.severity == "HIGH"
    assert report.root_cause == "UNHANDLED_TOOL_FAULT"
    assert report.fault_inception_step == 1
    assert len(report.blast_radius_mutations) == 1
    assert report.blast_radius_mutations[0]["actor"] == "delete_database"
    md = report.to_markdown()
    assert "Blast Radius Assessment" in md
    assert "Step #1" in md


def test_post_mortem_oscillation_detection(tmp_path: Path):
    rec = FlightRecorder(agent_id="looping-bot")
    rec.record("tool_call", "tool_a", {"x": 1}, {"y": 1})
    rec.record("tool_call", "tool_b", {"x": 2}, {"y": 2})
    rec.record("tool_call", "tool_a", {"x": 1}, {"y": 1})
    rec.record("tool_call", "tool_b", {"x": 2}, {"y": 2})
    cassette = tmp_path / "loop.cassette.json"
    rec.save(cassette)

    analyzer = FlightPostMortemAnalyzer()
    report = analyzer.analyze(cassette)

    assert report.severity == "CRITICAL"
    assert report.root_cause == "OSCILLATION_TRAP"
    assert report.fault_inception_step == 0
