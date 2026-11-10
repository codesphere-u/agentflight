"""
tests/test_cli_extensions.py
============================
Unit tests for CLI subcommands: `ci`, `post-mortem`, and `fix`.
"""

from __future__ import annotations

import json
from pathlib import Path
from agentflight.cli import main
from agentflight.recorder import FlightRecorder


def test_cli_ci_default_showcase():
    ret = main(["ci"])
    assert ret == 0


def test_cli_fix_command(tmp_path: Path):
    in_file = tmp_path / "flawed.json"
    out_file = tmp_path / "hardened.json"
    flawed_data = [
        {"name": "fetch_info", "description": "run", "inputSchema": {"properties": {"key": {}}}}
    ]
    with open(in_file, "w") as f:
        json.dump(flawed_data, f)

    ret = main(["fix", str(in_file), "--output", str(out_file)])
    assert ret == 0
    assert out_file.exists()

    with open(out_file) as f:
        data = json.load(f)
    assert data[0]["inputSchema"]["properties"]["key"]["type"] == "string"


def test_cli_post_mortem_command(tmp_path: Path):
    rec = FlightRecorder(agent_id="cli-bot")
    rec.record("tool_call", "test_step", {"a": 1}, {"b": 2})
    cassette = tmp_path / "cli_test.cassette.json"
    rec.save(cassette)

    ret = main(["post-mortem", str(cassette), "--json"])
    assert ret == 0
