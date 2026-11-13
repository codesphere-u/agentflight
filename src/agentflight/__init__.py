"""
agentflight
===========
AI Agent Black-Box Flight Recorder, Deterministic Trajectory Replay,
Loop/Cost Circuit Breaker & MCP Tool-Smell Linter.
"""

from ._version import __version__
from .diff import (
    TrajectoryDifferentialAnalyzer,
    TrajectoryDiffReport,
    compare_cassettes,
    compute_lcs_length,
    compute_levenshtein_distance,
)
from .eval import StepDiffItem, TrajectoryEvaluator, diff_trajectories
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
from .mcp_server import MCP_TOOLS, AgentFlightMCPServer
from .otel_export import OTelSpanPayload, export_cassette_to_otel
from .post_mortem import FlightPostMortemAnalyzer, IncidentReport
from .providers import get_provider, list_providers, register_provider
from .providers.openany import (
    OpenAnyAuthError,
    OpenAnyBudgetExceededError,
    OpenAnyConfig,
    OpenAnyError,
    OpenAnyInsufficientBalanceError,
    OpenAnyProvider,
    OpenAnyRateLimitError,
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
from .redact import contains_sensitive_data, redact_cassette, redact_sensitive
from .schema_optimizer import SchemaOptimizationResult, ToolSchemaOptimizer
from .testing import FlightSession, flight_test
from .wrappers import FlightCallbackHandler, wrap_anthropic, wrap_callable, wrap_openai

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
    "TrajectoryDifferentialAnalyzer",
    "TrajectoryDiffReport",
    "compare_cassettes",
    "compute_levenshtein_distance",
    "compute_lcs_length",
    "StepDiffItem",
    "diff_trajectories",
    "OTelSpanPayload",
    "export_cassette_to_otel",
    "AgentFlightMCPServer",
    "MCP_TOOLS",
    "OpenAnyProvider",
    "OpenAnyConfig",
    "OpenAnyError",
    "OpenAnyAuthError",
    "OpenAnyBudgetExceededError",
    "OpenAnyInsufficientBalanceError",
    "OpenAnyRateLimitError",
    "get_provider",
    "list_providers",
    "register_provider",
    "FlightSession",
    "flight_test",
    "FlightPostMortemAnalyzer",
    "IncidentReport",
    "ToolSchemaOptimizer",
    "SchemaOptimizationResult",
    "FlightCallbackHandler",
    "wrap_openai",
    "wrap_anthropic",
    "wrap_callable",
    "redact_sensitive",
    "redact_cassette",
    "contains_sensitive_data",
]
