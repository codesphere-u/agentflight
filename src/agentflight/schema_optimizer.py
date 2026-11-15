"""
agentflight.schema_optimizer
============================
Automated Tool Schema Repair & Hardening Engine for MCP and Agent Tools.

Automatically transforms flawed, smelly tool schemas into Gold-Standard
Glama TDQS & Anthropic compliant schemas with strict types, parameter bounds,
safe defaults, and zero ambiguity.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .linter import ToolSmellLinter, _compute_schema_depth, estimate_schema_tokens

READ_ONLY_PREFIXES = ("get_", "fetch_", "list_", "read_", "search_", "find_", "lookup_", "describe_", "check_")
DESTRUCTIVE_PREFIXES = ("delete_", "remove_", "drop_", "purge_", "terminate_", "destroy_")
MUTATION_PREFIXES = ("create_", "insert_", "update_", "modify_", "patch_", "post_", "charge_", "send_")
_VERBOSE_PREFIX_RE = re.compile(
    r"^(?:Executes|Specifies\s+the|Provides\s+a(?:n)?|Returns\s+an?\s+object\s+containing)\s+",
    re.IGNORECASE,
)


def _compact_prose(text: str, *, min_keep: int = 4) -> str:
    """Collapse redundant whitespace and verbose lead-in boilerplate without dropping meaning."""
    collapsed = " ".join(text.split())
    stripped = _VERBOSE_PREFIX_RE.sub("", collapsed).strip()
    if len(stripped) >= min_keep:
        return stripped[0].upper() + stripped[1:] if len(stripped) > 1 else stripped.upper()
    return collapsed


def _simplify_nullable_anyof(node: Dict[str, Any], mods: List[str], label: str) -> None:
    """Convert trivial 2-branch `anyOf: [{type: T}, {type: null}]` into Draft 2020-12 `type: [T, null]`."""
    variants = node.get("anyOf")
    if not isinstance(variants, list) or len(variants) != 2:
        return
    non_null = [v for v in variants if isinstance(v, dict) and v != {"type": "null"}]
    nulls = [v for v in variants if v == {"type": "null"}]
    if len(non_null) != 1 or len(nulls) != 1:
        return
    primary = non_null[0]
    primary_type = primary.get("type")
    if not isinstance(primary_type, str) or any(k in primary for k in ("anyOf", "oneOf", "allOf")):
        return
    node.pop("anyOf", None)
    for k, v in primary.items():
        if k == "type":
            node["type"] = [primary_type, "null"]
        elif k not in node:
            node[k] = copy.deepcopy(v)
    mods.append(f"Flattened nullable anyOf on '{label}' into type list")


def _compact_schema_node(node: Any, mods: List[str], path: str = "root", *, is_root: bool = False) -> None:
    """Recursively strip UI-only schema noise (titles, default additionalProperties, nullable wrappers)."""
    if not isinstance(node, dict):
        return

    # Strip UI-only JSON Schema titles everywhere inside schemas (preserves semantic keys).
    if "title" in node:
        node.pop("title", None)
        if not is_root:
            mods.append(f"Stripped display-only 'title' on '{path}'")

    # `additionalProperties: true` is JSON Schema's default behavior.
    if node.get("additionalProperties") is True:
        node.pop("additionalProperties", None)

    if isinstance(node.get("description"), str):
        desc = node["description"].strip()
        if not desc:
            node.pop("description", None)
        else:
            tight = _compact_prose(desc, min_keep=4)
            if tight != node["description"]:
                node["description"] = tight

    _simplify_nullable_anyof(node, mods, path)

    props = node.get("properties")
    if isinstance(props, dict):
        for prop_name, prop_val in props.items():
            _compact_schema_node(prop_val, mods, f"{path}.{prop_name}")

    items = node.get("items")
    if isinstance(items, dict):
        _compact_schema_node(items, mods, f"{path}[]")

    defs = node.get("$defs")
    if isinstance(defs, dict):
        for def_name, def_val in list(defs.items()):
            _compact_schema_node(def_val, mods, f"$defs.{def_name}")
        if not defs:
            node.pop("$defs", None)


def _inline_single_defs(root_schema: Dict[str, Any], mods: List[str]) -> None:
    """Inline `$defs` entries referenced safely once when doing so keeps nesting depth <= 3."""
    defs = root_schema.get("$defs")
    if not isinstance(defs, dict) or not defs:
        return

    ref_counts: Dict[str, int] = {}

    def _count_refs(obj: Any) -> None:
        if isinstance(obj, dict):
            ref = obj.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                key = ref[len("#/$defs/") :]
                ref_counts[key] = ref_counts.get(key, 0) + 1
            for k, v in obj.items():
                if k != "$defs":
                    _count_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                _count_refs(item)

    _count_refs(root_schema)

    def _replace_refs(obj: Any, inlined: Dict[str, Dict[str, Any]]) -> None:
        if isinstance(obj, dict):
            ref = obj.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target = ref[len("#/$defs/") :]
                if target in inlined:
                    merged = copy.deepcopy(inlined[target])
                    extra = {k: v for k, v in obj.items() if k != "$ref"}
                    obj.clear()
                    obj.update(merged)
                    obj.update(extra)
            for k, v in obj.items():
                if k != "$defs":
                    _replace_refs(v, inlined)
        elif isinstance(obj, list):
            for item in obj:
                _replace_refs(item, inlined)

    candidates: Dict[str, Dict[str, Any]] = {}
    for def_name, def_body in list(defs.items()):
        count = ref_counts.get(def_name, 0)
        if count == 0:
            defs.pop(def_name, None)
            mods.append(f"Removed unreferenced '$defs.{def_name}'")
        elif count == 1 and isinstance(def_body, dict) and "#/$defs/" not in str(def_body):
            candidate_root = copy.deepcopy(root_schema)
            _replace_refs(candidate_root, {def_name: def_body})
            if _compute_schema_depth(candidate_root) <= 3:
                candidates[def_name] = def_body

    if candidates:
        _replace_refs(root_schema, candidates)
        for def_name in candidates:
            defs.pop(def_name, None)
            mods.append(f"Inlined single-use '$defs.{def_name}' to flatten schema")
    if not defs:
        root_schema.pop("$defs", None)


@dataclass
class SchemaOptimizationResult:
    original_tool: Dict[str, Any]
    hardened_tool: Dict[str, Any]
    modifications_applied: List[str]
    original_token_estimate: int
    hardened_token_estimate: int
    original_smell_count: int
    hardened_smell_count: int

    @property
    def token_delta(self) -> int:
        return self.hardened_token_estimate - self.original_token_estimate

    @property
    def token_savings(self) -> int:
        return max(0, self.original_token_estimate - self.hardened_token_estimate)

    @property
    def token_reduction_pct(self) -> float:
        if self.original_token_estimate <= 0:
            return 0.0
        return round((self.original_token_estimate - self.hardened_token_estimate) / self.original_token_estimate * 100.0, 2)

    @property
    def smells_resolved(self) -> int:
        return max(0, self.original_smell_count - self.hardened_smell_count)


class ToolSchemaOptimizer:
    """Repairs and optionally token-compacts MCP tool schemas into high-ergonomics definitions."""

    def __init__(self, *, compact: bool = False) -> None:
        self.compact = compact
        self.linter = ToolSmellLinter()

    def optimize_tool(self, tool_def: Dict[str, Any]) -> SchemaOptimizationResult:
        original = copy.deepcopy(tool_def)
        hardened = copy.deepcopy(tool_def)
        mods: List[str] = []

        orig_report = self.linter.lint([original])
        orig_tokens = estimate_schema_tokens(original)

        # 1. Clean & enrich tool name
        name = hardened.get("name", "").strip()
        if not name:
            hardened["name"] = "unnamed_tool"
            name = hardened["name"]
            mods.append("Added default tool name 'unnamed_tool'")

        # 2. Fix empty or vague description
        desc = hardened.get("description", "").strip()
        if len(desc) < 15 or desc.lower() in ("run", "tool", "do stuff", "executes"):
            human_name = name.replace("_", " ").title()
            if self.compact:
                hardened["description"] = f"{human_name} with validated parameters."
            else:
                hardened["description"] = (
                    f"Executes {human_name} operation. Provide required structured parameters to ensure deterministic agent evaluation."
                )
            mods.append(f"Expanded short description to informative specification ({len(hardened['description'])} chars)")
        elif self.compact:
            tight_desc = _compact_prose(desc, min_keep=15)
            if tight_desc != desc:
                hardened["description"] = tight_desc
                mods.append("Tightened tool description prose for token efficiency")

        # 3. Ensure inputSchema structure
        schema = hardened.setdefault("inputSchema", {})
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
            hardened["inputSchema"] = schema
            mods.append("Reconstructed root inputSchema as JSON schema object")

        if schema.get("type") != "object":
            schema["type"] = "object"
            mods.append("Enforced 'type': 'object' on inputSchema")

        props = schema.setdefault("properties", {})
        if not isinstance(props, dict):
            props = {}
            schema["properties"] = props
            mods.append("Initialized 'properties' dictionary")

        required = schema.setdefault("required", [])
        if not isinstance(required, list):
            schema["required"] = []
            required = schema["required"]

        # 4. Compact mode pre-pass: strip Pydantic display metadata & nullable anyOf, then inline single-use $defs
        if self.compact:
            _compact_schema_node(schema, mods, "inputSchema", is_root=True)
            _inline_single_defs(schema, mods)
            if isinstance(hardened.get("outputSchema"), dict):
                _compact_schema_node(hardened["outputSchema"], mods, "outputSchema", is_root=True)

        # 5. Property hardening
        for prop_name, prop_val in list(props.items()):
            if not isinstance(prop_val, dict):
                props[prop_name] = {"type": "string", "description": f"Parameter '{prop_name}'"}
                prop_val = props[prop_name]
                mods.append(f"Coerced property '{prop_name}' to typed object")

            # Missing type (preserve Draft 2020-12 type arrays and $ref definitions)
            if "type" not in prop_val and "$ref" not in prop_val:
                prop_val["type"] = "string"
                mods.append(f"Injected default 'type': 'string' for property '{prop_name}'")

            # Missing description (resolve $ref if already documented inside target def)
            prop_desc = str(prop_val.get("description") or "").strip()
            if not prop_desc and isinstance(prop_val.get("$ref"), str):
                ref_name = prop_val["$ref"].removeprefix("#/$defs/")
                ref_def = (schema.get("$defs") or {}).get(ref_name)
                if isinstance(ref_def, dict):
                    prop_desc = str(ref_def.get("description") or "").strip()
            if not prop_desc:
                if self.compact:
                    label = prop_name.replace("_", " ").strip()
                    prop_val["description"] = (label[0].upper() + label[1:]) if label else "Parameter"
                else:
                    prop_val["description"] = f"Specifies the {prop_name.replace('_', ' ')} value for the operation."
                mods.append(f"Generated descriptive documentation for parameter '{prop_name}'")

            # Add numeric bounds for common range properties
            if prop_val.get("type") in ("integer", "number"):
                if any(k in prop_name.lower() for k in ("limit", "count", "page_size", "max_results")):
                    if "minimum" not in prop_val:
                        prop_val["minimum"] = 1
                        mods.append(f"Set 'minimum': 1 boundary for parameter '{prop_name}'")
                    if "maximum" not in prop_val:
                        prop_val["maximum"] = 100
                        mods.append(f"Set 'maximum': 100 boundary for parameter '{prop_name}'")

            # Add array item bounds
            elif prop_val.get("type") == "array":
                if "items" not in prop_val:
                    prop_val["items"] = {"type": "string"}
                    mods.append(f"Injected default string item type for array property '{prop_name}'")
                if "maxItems" not in prop_val:
                    prop_val["maxItems"] = 50
                    mods.append(f"Bound array property '{prop_name}' with 'maxItems': 50")

        # 6. Ingest Glama & Anthropic compliant annotations
        annotations = hardened.setdefault("annotations", {})
        if not isinstance(annotations, dict):
            hardened["annotations"] = {}
            annotations = hardened["annotations"]

        if any(name.startswith(p) for p in READ_ONLY_PREFIXES):
            if "readOnlyHint" not in annotations:
                annotations["readOnlyHint"] = True
                annotations["idempotentHint"] = True
                mods.append("Tagged with 'readOnlyHint: true' and 'idempotentHint: true'")
        elif any(name.startswith(p) for p in DESTRUCTIVE_PREFIXES):
            if "destructiveHint" not in annotations:
                annotations["destructiveHint"] = True
                annotations["readOnlyHint"] = False
                mods.append("Tagged with 'destructiveHint: true'")
        elif any(name.startswith(p) for p in MUTATION_PREFIXES):
            if "readOnlyHint" not in annotations:
                annotations["readOnlyHint"] = False
                mods.append("Tagged with 'readOnlyHint: false'")

        hardened_report = self.linter.lint([hardened])
        hardened_tokens = estimate_schema_tokens(hardened)

        return SchemaOptimizationResult(
            original_tool=original,
            hardened_tool=hardened,
            modifications_applied=mods,
            original_token_estimate=orig_tokens,
            hardened_token_estimate=hardened_tokens,
            original_smell_count=len(orig_report.findings),
            hardened_smell_count=len(hardened_report.findings),
        )

    def optimize_tools(self, tools: Sequence[Dict[str, Any]]) -> List[SchemaOptimizationResult]:
        return [self.optimize_tool(t) for t in tools]


def compact_mcp_tools(tools: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Repair smells and compact token footprint across an entire MCP tool catalog."""
    linter = ToolSmellLinter()
    before_report = linter.lint(tools)
    results = ToolSchemaOptimizer(compact=True).optimize_tools(tools)
    compacted_tools = [r.hardened_tool for r in results]
    after_report = linter.lint(compacted_tools)
    before_tokens = before_report.estimated_tokens_per_turn
    after_tokens = after_report.estimated_tokens_per_turn
    saved = before_tokens - after_tokens
    pct = round((saved / before_tokens) * 100.0, 2) if before_tokens > 0 else 0.0
    return {
        "tool_count": len(tools),
        "before_tokens_per_turn": before_tokens,
        "after_tokens_per_turn": after_tokens,
        "tokens_saved_per_turn": saved,
        "token_reduction_pct": pct,
        "before_score": before_report.ergonomics_score,
        "before_grade": before_report.grade,
        "before_findings": len(before_report.findings),
        "after_score": after_report.ergonomics_score,
        "after_grade": after_report.grade,
        "after_findings": len(after_report.findings),
        "tools": compacted_tools,
    }
