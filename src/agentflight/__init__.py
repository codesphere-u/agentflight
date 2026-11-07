"""
agentflight
===========
AI Agent Black-Box Flight Recorder, Deterministic Trajectory Replay,
Loop/Cost Circuit Breaker & MCP Tool-Smell Linter.
"""

from .eval import StepDiffItem, TrajectoryDiffReport, TrajectoryEvaluator, diff_trajectories
from .guard import CircuitBreakerStats, CircuitBreakerTripped, TrajectoryCircuitBreaker
from .linter import (
    RULE_CATALOG,
    SHOWCASE_FLAWED_MCP_TOOLS,
    SHOWCASE_HARDENED_MCP_TOOLS,
    ToolLintReport,
    ToolSmellFinding,
    ToolSmellLinter,
    estimate_schema_tokens,
)
from .recorder import (
    GENESIS_HASH,
    CassetteReplayer,
    CassetteTamperError,
    FlightRecorder,
    TrajectoryDivergenceError,
    TrajectorySpan,
    canonical_hash,
    canonical_json,
    verify_cassette,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "GENESIS_HASH",
    "FlightRecorder",
    "CassetteReplayer",
    "TrajectorySpan",
    "CassetteTamperError",
    "TrajectoryDivergenceError",
    "verify_cassette",
    "canonical_json",
    "canonical_hash",
    "ToolSmellLinter",
    "ToolLintReport",
    "ToolSmellFinding",
    "RULE_CATALOG",
    "SHOWCASE_FLAWED_MCP_TOOLS",
    "SHOWCASE_HARDENED_MCP_TOOLS",
    "estimate_schema_tokens",
    "TrajectoryCircuitBreaker",
    "CircuitBreakerTripped",
    "CircuitBreakerStats",
    "TrajectoryEvaluator",
    "TrajectoryDiffReport",
    "StepDiffItem",
    "diff_trajectories",
]
