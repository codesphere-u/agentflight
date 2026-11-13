"""
agentflight.linter
==================
MCP & Agent Tool-Schema Ergonomics Linter (`ToolSmellLinter`).

Statically analyzes Model Context Protocol (MCP) tool definitions (`inputSchema`)
or OpenAI/Anthropic function schemas across 10 deterministic ergonomics rules
(`TS001`–`TS010`), computes an Agent Ergonomics Score (0–100), estimates token
footprint per turn, and generates actionable remediation guidance.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple

Severity = Literal["error", "warning", "info"]

RULE_CATALOG: Dict[str, Dict[str, Any]] = {
    "TS001": {
        "title": "Missing or Ultra-Short Tool Description",
        "severity": "error",
        "penalty": 12,
        "summary": "Tool description is missing or shorter than 15 characters, leaving the model without invocation criteria.",
    },
    "TS002": {
        "title": "Property Missing Description",
        "severity": "warning",
        "penalty": 5,
        "summary": "A schema property in inputSchema.properties lacks a semantic description.",
    },
    "TS003": {
        "title": "Deeply Nested Input Schema (Depth > 3)",
        "severity": "warning",
        "penalty": 8,
        "summary": "Object/array nesting exceeds depth 3, degrading tool-call JSON reliability on fast/small models.",
    },
    "TS004": {
        "title": "Excessive Top-Level Parameter Count (> 8)",
        "severity": "warning",
        "penalty": 7,
        "summary": "Tool exposes more than 8 top-level properties, increasing parameter hallucination rates.",
    },
    "TS005": {
        "title": "Ambiguous Boolean Flag Name",
        "severity": "warning",
        "penalty": 5,
        "summary": "Boolean parameter uses an opaque name (flag, mode, option, data, value) without clear polarity.",
    },
    "TS006": {
        "title": "Unconstrained Finite-Set String Parameter",
        "severity": "warning",
        "penalty": 6,
        "summary": "String parameter with finite-set semantics (status, sort, format, env, role, type) omits enum or pattern.",
    },
    "TS007": {
        "title": "Missing `required` Array on Non-Empty Schema",
        "severity": "warning",
        "penalty": 6,
        "summary": "Schema defines properties but omits the `required` array, causing models to omit mandatory fields.",
    },
    "TS008": {
        "title": "High Lexical Overlap Between Tools (Confusion Hazard)",
        "severity": "error",
        "penalty": 10,
        "summary": "Two tools in the suite share highly overlapping names/descriptions, causing nondeterministic tool routing.",
    },
    "TS009": {
        "title": "Bloated Schema Token Footprint (> 450 Tokens)",
        "severity": "warning",
        "penalty": 7,
        "summary": "Single tool schema exceeds 450 estimated tokens, inflating context window overhead on every turn.",
    },
    "TS010": {
        "title": "Destructive Tool Missing Safety / Confirmation Guard",
        "severity": "error",
        "penalty": 10,
        "summary": "Destructive tool (delete_*, drop_*, remove_*, transfer_*, exec_*) lacks confirmation/dry_run/idempotency guard or safety warning.",
    },
}

AMBIGUOUS_BOOLEAN_NAMES: Set[str] = {
    "flag",
    "mode",
    "option",
    "data",
    "value",
    "switch",
    "toggle",
    "bool",
}

FINITE_SET_PARAM_NAMES: Set[str] = {
    "status",
    "sort",
    "sort_by",
    "order",
    "format",
    "env",
    "environment",
    "role",
    "type",
    "severity",
    "priority",
    "state",
}

DESTRUCTIVE_PREFIXES: Tuple[str, ...] = (
    "delete_",
    "drop_",
    "remove_",
    "transfer_",
    "exec_",
    "destroy_",
    "purge_",
    "truncate_",
)

SAFETY_PARAM_NAMES: Set[str] = {
    "confirm",
    "confirmed",
    "dry_run",
    "idempotency_key",
    "force",
    "approval_token",
}

SAFETY_DESCRIPTION_KEYWORDS: Tuple[str, ...] = (
    "irreversible",
    "destructive",
    "confirm",
    "confirmation",
    "idempotent",
    "idempotency",
    "dry_run",
    "dry-run",
    "caution",
    "permanently",
)

STOPWORDS: Set[str] = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "in",
    "on",
    "of",
    "and",
    "or",
    "with",
    "by",
    "from",
    "this",
    "that",
    "is",
    "are",
    "be",
}


@dataclass(frozen=True)
class ToolSmellFinding:
    """Single lint finding emitted by `ToolSmellLinter`."""

    rule_id: str
    severity: Severity
    tool_name: str
    message: str
    remediation: str
    property_path: Optional[str] = None
    penalty: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolLintReport:
    """Complete ergonomics report for a suite of MCP / function-calling tools."""

    tool_count: int
    ergonomics_score: int
    grade: str
    estimated_tokens_per_turn: int
    tool_token_estimates: Dict[str, int]
    findings: List[ToolSmellFinding]
    rule_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_count": self.tool_count,
            "ergonomics_score": self.ergonomics_score,
            "grade": self.grade,
            "estimated_tokens_per_turn": self.estimated_tokens_per_turn,
            "tool_token_estimates": self.tool_token_estimates,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "rule_counts": self.rule_counts,
            "findings": [f.to_dict() for f in self.findings],
        }


def _normalize_tool_def(raw: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """
    Normalize MCP (`inputSchema`), OpenAI (`function.parameters`), or Anthropic (`input_schema`)
    tool definitions into `(name, description, input_schema)`.
    """
    if "function" in raw and isinstance(raw["function"], dict):
        fn = raw["function"]
        name = str(fn.get("name", "unnamed_tool"))
        desc = str(fn.get("description") or "")
        raw_params = fn.get("parameters")
        schema = dict(raw_params) if isinstance(raw_params, dict) else {}
        return name, desc, schema

    name = str(raw.get("name", "unnamed_tool"))
    desc = str(raw.get("description") or "")
    raw_schema = raw.get("inputSchema") or raw.get("input_schema") or raw.get("parameters")
    schema = dict(raw_schema) if isinstance(raw_schema, dict) else {}
    return name, desc, schema


def estimate_schema_tokens(tool_def: Dict[str, Any]) -> int:
    """
    Estimate the LLM prompt token footprint of a single tool definition.
    Uses a deterministic JSON structural + BPE-like word/punctuation heuristic (~3.6 chars/token).
    """
    serialized = json.dumps(tool_def, sort_keys=True, separators=(",", ":"))
    return max(1, math.ceil(len(serialized) / 3.6))


def _resolve_schema_ref(ref: str, root_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve an in-schema JSON Pointer reference (e.g. '#/$defs/Foo' or '#/definitions/Foo')."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    cur: Any = root_schema
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if isinstance(cur, dict) else None


def _compute_schema_depth(
    schema: Any,
    current_depth: int = 0,
    root_schema: Optional[Dict[str, Any]] = None,
    visited_refs: Optional[Set[str]] = None,
) -> int:
    """Compute maximum object/array nesting depth of a JSON Schema, resolving $ref pointers."""
    if not isinstance(schema, dict):
        return current_depth

    if root_schema is None:
        root_schema = schema
    if visited_refs is None:
        visited_refs = set()

    max_d = current_depth

    # Follow $ref if present and not visited
    if "$ref" in schema and isinstance(schema["$ref"], str):
        ref = schema["$ref"]
        if ref not in visited_refs:
            visited_refs = set(visited_refs)
            visited_refs.add(ref)
            resolved = _resolve_schema_ref(ref, root_schema)
            if resolved:
                max_d = max(max_d, _compute_schema_depth(resolved, current_depth, root_schema, visited_refs))

    props = schema.get("properties")
    if isinstance(props, dict) and props:
        for sub in props.values():
            max_d = max(max_d, _compute_schema_depth(sub, current_depth + 1, root_schema, visited_refs))

    items = schema.get("items")
    if isinstance(items, dict):
        max_d = max(max_d, _compute_schema_depth(items, current_depth + 1, root_schema, visited_refs))

    for combiner in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(combiner)
        if isinstance(variants, list):
            for v in variants:
                max_d = max(max_d, _compute_schema_depth(v, current_depth + 1, root_schema, visited_refs))

    return max_d


def _tokenize_text(text: str) -> List[str]:
    """Split camelCase/snake_case and prose into normalized lowercase tokens."""
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    words = re.findall(r"[a-zA-Z0-9]+", expanded.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _cosine_similarity(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Compute bag-of-words cosine similarity between two token lists."""
    if not tokens_a or not tokens_b:
        return 0.0
    freq_a: Dict[str, int] = {}
    freq_b: Dict[str, int] = {}
    for t in tokens_a:
        freq_a[t] = freq_a.get(t, 0) + 1
    for t in tokens_b:
        freq_b[t] = freq_b.get(t, 0) + 1

    common = set(freq_a.keys()) & set(freq_b.keys())
    dot = sum(freq_a[k] * freq_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in freq_a.values()))
    norm_b = math.sqrt(sum(v * v for v in freq_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class ToolSmellLinter:
    """
    Deterministic 10-Rule MCP & Agent Tool-Schema Ergonomics Linter (`TS001`–`TS010`).
    """

    def __init__(
        self,
        *,
        min_description_chars: int = 15,
        max_schema_depth: int = 3,
        max_properties: int = 8,
        similarity_threshold: float = 0.72,
        max_tool_tokens: int = 450,
    ) -> None:
        self.min_description_chars = min_description_chars
        self.max_schema_depth = max_schema_depth
        self.max_properties = max_properties
        self.similarity_threshold = similarity_threshold
        self.max_tool_tokens = max_tool_tokens

    def lint(self, tools: Sequence[Dict[str, Any]]) -> ToolLintReport:
        """Analyze a list of MCP or function-calling tool schemas and return a `ToolLintReport`."""
        findings: List[ToolSmellFinding] = []
        tool_token_estimates: Dict[str, int] = {}
        normalized_tools: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]] = []

        for raw in tools:
            name, desc, schema = _normalize_tool_def(raw)
            normalized_tools.append((name, desc, schema, raw))
            est_tokens = estimate_schema_tokens(raw)
            tool_token_estimates[name] = est_tokens

            # TS001: Missing or ultra-short (<15 chars) tool description
            clean_desc = desc.strip()
            if len(clean_desc) < self.min_description_chars:
                findings.append(
                    ToolSmellFinding(
                        rule_id="TS001",
                        severity="error",
                        tool_name=name,
                        message=(
                            f"Tool '{name}' has a missing or ultra-short description "
                            f"({len(clean_desc)} chars < {self.min_description_chars} min)."
                        ),
                        remediation=(
                            "Provide a clear 1-2 sentence description stating what the tool does, "
                            "when the agent should call it, and what it returns."
                        ),
                        penalty=RULE_CATALOG["TS001"]["penalty"],
                    )
                )

            props = schema.get("properties")
            if not isinstance(props, dict):
                props = {}

            # TS007: Missing `required` array when properties exist
            if props and "required" not in schema:
                findings.append(
                    ToolSmellFinding(
                        rule_id="TS007",
                        severity="warning",
                        tool_name=name,
                        message=(
                            f"Tool '{name}' defines {len(props)} properties but omits the top-level "
                            f"'required' array."
                        ),
                        remediation=(
                            "Explicitly declare `\"required\": [...]` in `inputSchema` (use `[]` if all "
                            "parameters are genuinely optional) to prevent argument omission."
                        ),
                        penalty=RULE_CATALOG["TS007"]["penalty"],
                    )
                )

            # TS004: Excessive parameter count (> 8 top-level properties)
            if len(props) > self.max_properties:
                findings.append(
                    ToolSmellFinding(
                        rule_id="TS004",
                        severity="warning",
                        tool_name=name,
                        message=(
                            f"Tool '{name}' exposes {len(props)} top-level properties "
                            f"(exceeds max recommended {self.max_properties})."
                        ),
                        remediation=(
                            "Split the tool into narrower intent-specific tools or group related filter "
                            "fields into a cohesive query object."
                        ),
                        penalty=RULE_CATALOG["TS004"]["penalty"],
                    )
                )

            # TS003: Deeply nested schema (depth > 3)
            depth = _compute_schema_depth(schema, 0)
            if depth > self.max_schema_depth:
                findings.append(
                    ToolSmellFinding(
                        rule_id="TS003",
                        severity="warning",
                        tool_name=name,
                        message=(
                            f"Tool '{name}' inputSchema has nesting depth {depth} "
                            f"(exceeds max recommended depth {self.max_schema_depth})."
                        ),
                        remediation=(
                            "Flatten deeply nested input objects to <= 2 levels so smaller/faster "
                            "models can reliably serialize tool arguments."
                        ),
                        penalty=RULE_CATALOG["TS003"]["penalty"],
                    )
                )

            # Inspect individual properties for TS002, TS005, TS006
            for prop_name, raw_prop_schema in props.items():
                if not isinstance(raw_prop_schema, dict):
                    continue

                # Resolve $ref if present to inherit type, enum, description from $defs/definitions
                prop_schema = dict(raw_prop_schema)
                if "$ref" in raw_prop_schema and isinstance(raw_prop_schema["$ref"], str):
                    resolved = _resolve_schema_ref(raw_prop_schema["$ref"], schema)
                    if resolved:
                        merged = dict(resolved)
                        merged.update(raw_prop_schema)
                        prop_schema = merged

                prop_desc = str(prop_schema.get("description") or "").strip()
                prop_type = prop_schema.get("type")

                # TS002: Property missing description
                if not prop_desc:
                    findings.append(
                        ToolSmellFinding(
                            rule_id="TS002",
                            severity="warning",
                            tool_name=name,
                            property_path=f"properties.{prop_name}",
                            message=f"Property '{prop_name}' on tool '{name}' is missing a `description`.",
                            remediation=(
                                f"Add a concise `description` to `inputSchema.properties.{prop_name}` "
                                "including format examples or unit expectations."
                            ),
                            penalty=RULE_CATALOG["TS002"]["penalty"],
                        )
                    )

                # TS005: Ambiguous boolean flag name
                if prop_type == "boolean" and prop_name.lower() in AMBIGUOUS_BOOLEAN_NAMES:
                    findings.append(
                        ToolSmellFinding(
                            rule_id="TS005",
                            severity="warning",
                            tool_name=name,
                            property_path=f"properties.{prop_name}",
                            message=(
                                f"Boolean property '{prop_name}' on tool '{name}' uses an ambiguous "
                                "flag name without clear polarity."
                            ),
                            remediation=(
                                f"Rename '{prop_name}' to a predicate verb phrase such as "
                                "`include_archived`, `dry_run`, or `recursive`."
                            ),
                            penalty=RULE_CATALOG["TS005"]["penalty"],
                        )
                    )

                # TS006: Unconstrained string parameter with finite-set naming
                if (
                    prop_type == "string"
                    and prop_name.lower() in FINITE_SET_PARAM_NAMES
                    and "enum" not in prop_schema
                    and "pattern" not in prop_schema
                ):
                    findings.append(
                        ToolSmellFinding(
                            rule_id="TS006",
                            severity="warning",
                            tool_name=name,
                            property_path=f"properties.{prop_name}",
                            message=(
                                f"Finite-set string property '{prop_name}' on tool '{name}' lacks "
                                "an `enum` or regex `pattern` constraint."
                            ),
                            remediation=(
                                f"Constrain `inputSchema.properties.{prop_name}` with `\"enum\": [...]` "
                                "so the model cannot hallucinate unsupported values."
                            ),
                            penalty=RULE_CATALOG["TS006"]["penalty"],
                        )
                    )

            # TS009: Bloated schema token footprint (> 450 estimated tokens)
            if est_tokens > self.max_tool_tokens:
                findings.append(
                    ToolSmellFinding(
                        rule_id="TS009",
                        severity="warning",
                        tool_name=name,
                        message=(
                            f"Tool '{name}' consumes ~{est_tokens} tokens "
                            f"(exceeds {self.max_tool_tokens} token budget)."
                        ),
                        remediation=(
                            "Trim verbose prose in property descriptions, remove redundant examples, "
                            "or split the tool schema to reduce per-turn prompt token overhead."
                        ),
                        penalty=RULE_CATALOG["TS009"]["penalty"],
                    )
                )

            # TS010: Destructive tool name missing confirmation/idempotency parameter or safety hint
            lower_name = name.lower()
            if lower_name.startswith(DESTRUCTIVE_PREFIXES):
                has_safety_param = any(p.lower() in SAFETY_PARAM_NAMES for p in props.keys())
                lower_desc = clean_desc.lower()
                has_safety_hint = any(kw in lower_desc for kw in SAFETY_DESCRIPTION_KEYWORDS)
                if not (has_safety_param or has_safety_hint):
                    findings.append(
                        ToolSmellFinding(
                            rule_id="TS010",
                            severity="error",
                            tool_name=name,
                            message=(
                                f"Destructive tool '{name}' lacks an explicit confirmation/dry_run/"
                                "idempotency parameter or safety warning in its description."
                            ),
                            remediation=(
                                "Add a `confirm: boolean` / `dry_run: boolean` / `idempotency_key: string` "
                                "parameter or document irreversibility and confirmation rules in `description`."
                            ),
                            penalty=RULE_CATALOG["TS010"]["penalty"],
                        )
                    )

        # TS008: High lexical overlap / cosine similarity between two tool names/descriptions
        for i in range(len(normalized_tools)):
            name_a, desc_a, _, _ = normalized_tools[i]
            tokens_a = _tokenize_text(f"{name_a} {name_a} {desc_a}")
            for j in range(i + 1, len(normalized_tools)):
                name_b, desc_b, _, _ = normalized_tools[j]
                tokens_b = _tokenize_text(f"{name_b} {name_b} {desc_b}")
                sim = _cosine_similarity(tokens_a, tokens_b)
                if sim >= self.similarity_threshold:
                    findings.append(
                        ToolSmellFinding(
                            rule_id="TS008",
                            severity="error",
                            tool_name=f"{name_a} <-> {name_b}",
                            message=(
                                f"High lexical similarity ({sim:.2f} >= {self.similarity_threshold:.2f}) "
                                f"between tools '{name_a}' and '{name_b}' creates a tool-selection confusion hazard."
                            ),
                            remediation=(
                                f"Merge '{name_a}' and '{name_b}' into a single parameterized tool or "
                                "sharply differentiate their names and invocation preconditions."
                            ),
                            penalty=RULE_CATALOG["TS008"]["penalty"],
                        )
                    )

        total_penalty = sum(f.penalty for f in findings)
        # Scale penalty mildly by suite size if multiple tools are present, bounded to [0, 100]
        score = max(0, min(100, 100 - total_penalty))
        rule_counts: Dict[str, int] = {}
        for f in findings:
            rule_counts[f.rule_id] = rule_counts.get(f.rule_id, 0) + 1

        return ToolLintReport(
            tool_count=len(tools),
            ergonomics_score=score,
            grade=_score_to_grade(score),
            estimated_tokens_per_turn=sum(tool_token_estimates.values()),
            tool_token_estimates=tool_token_estimates,
            findings=findings,
            rule_counts=rule_counts,
        )


SHOWCASE_FLAWED_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "delete_user",
        "description": "Deletes user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "flag": {"type": "boolean", "description": "Some boolean flag"},
                "status": {"type": "string", "description": "Account status filter"},
                "p4": {"type": "string", "description": "Extra param 4"},
                "p5": {"type": "string", "description": "Extra param 5"},
                "p6": {"type": "string", "description": "Extra param 6"},
                "p7": {"type": "string", "description": "Extra param 7"},
                "p8": {"type": "string", "description": "Extra param 8"},
                "nested_filter": {
                    "type": "object",
                    "description": "Deep filter object",
                    "properties": {
                        "level1": {
                            "type": "object",
                            "properties": {
                                "level2": {
                                    "type": "object",
                                    "properties": {
                                        "level3": {"type": "string"}
                                    },
                                }
                            },
                        }
                    },
                },
            },
        },
    },
    {
        "name": "search_customer_records",
        "description": "Search customer records in the CRM database by query string and filters.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query string for customer records."}
            },
        },
    },
    {
        "name": "find_customer_records",
        "description": "Search customer records in the CRM database by query string and filter criteria.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Query string to search customer records."}
            },
        },
    },
]

SHOWCASE_HARDENED_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "delete_user_account",
        "description": (
            "Permanently deactivate or purge a user account by ID. "
            "Destructive and irreversible when dry_run is false; requires explicit confirmation."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["user_id", "confirm", "dry_run"],
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Unique UUID of the target user account (e.g. 'usr_94a1').",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be set to true after explicit human confirmation.",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, validates deletion impact without mutating state.",
                },
                "status": {
                    "type": "string",
                    "enum": ["suspended", "pending_deletion", "inactive"],
                    "description": "Expected current lifecycle status required before deletion.",
                },
            },
        },
    },
    {
        "name": "search_crm_customers",
        "description": (
            "Query CRM customer profiles by email domain, lifecycle stage, or full-text name match."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Full-text search string matching customer name or email.",
                },
                "sort": {
                    "type": "string",
                    "enum": ["created_asc", "created_desc", "mrr_desc"],
                    "description": "Sort order for returned CRM customer records.",
                },
            },
        },
    },
]
