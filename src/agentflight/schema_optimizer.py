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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .linter import ToolSmellLinter, estimate_schema_tokens

READ_ONLY_PREFIXES = ("get_", "fetch_", "list_", "read_", "search_", "find_", "lookup_", "describe_", "check_")
DESTRUCTIVE_PREFIXES = ("delete_", "remove_", "drop_", "purge_", "terminate_", "destroy_")
MUTATION_PREFIXES = ("create_", "insert_", "update_", "modify_", "patch_", "post_", "charge_", "send_")


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
    def smells_resolved(self) -> int:
        return max(0, self.original_smell_count - self.hardened_smell_count)


class ToolSchemaOptimizer:
    """Repairs smelly MCP tool schemas into high-ergonomics, safe definitions."""

    def __init__(self) -> None:
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
            hardened["description"] = (
                f"Executes {human_name} operation. Provide required structured parameters to ensure deterministic agent evaluation."
            )
            mods.append(f"Expanded short description to informative specification ({len(hardened['description'])} chars)")

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

        # 4. Property hardening
        for prop_name, prop_val in list(props.items()):
            if not isinstance(prop_val, dict):
                props[prop_name] = {"type": "string", "description": f"Parameter '{prop_name}'"}
                prop_val = props[prop_name]
                mods.append(f"Coerced property '{prop_name}' to typed object")

            # Missing type
            if "type" not in prop_val:
                prop_val["type"] = "string"
                mods.append(f"Injected default 'type': 'string' for property '{prop_name}'")

            # Missing description
            prop_desc = prop_val.get("description", "").strip()
            if not prop_desc:
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

        # 5. Ingest Glama & Anthropic compliant annotations
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
