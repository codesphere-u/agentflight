"""
tests/test_schema_optimizer.py
==============================
Unit tests for `agentflight.schema_optimizer` (ToolSchemaOptimizer).
"""

from __future__ import annotations

from agentflight.schema_optimizer import ToolSchemaOptimizer, compact_mcp_tools


def test_schema_optimizer_hardens_flawed_tool():
    optimizer = ToolSchemaOptimizer()
    flawed = {
        "name": "get_customer_records",
        "description": "get",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {},  # missing type and description
                "limit": {"type": "integer"},  # missing bounds and description
                "tags": {"type": "array"},  # missing items and maxItems
            },
        },
    }

    res = optimizer.optimize_tool(flawed)
    hardened = res.hardened_tool

    # 1. Description enriched
    assert len(hardened["description"]) > 20
    assert "Customer Records" in hardened["description"]

    # 2. Properties hardened
    props = hardened["inputSchema"]["properties"]
    assert props["customer_id"]["type"] == "string"
    assert "description" in props["customer_id"]

    assert props["limit"]["minimum"] == 1
    assert props["limit"]["maximum"] == 100
    assert "description" in props["limit"]

    assert props["tags"]["items"]["type"] == "string"
    assert props["tags"]["maxItems"] == 50

    # 3. Annotations
    assert hardened["annotations"]["readOnlyHint"] is True
    assert hardened["annotations"]["idempotentHint"] is True

    assert len(res.modifications_applied) >= 5


def test_schema_optimizer_destructive_tool():
    optimizer = ToolSchemaOptimizer()
    flawed = {
        "name": "delete_user",
        "description": "deletes user",
        "inputSchema": {
            "properties": {
                "uid": {"type": "string"},
            }
        },
    }

    res = optimizer.optimize_tool(flawed)
    hardened = res.hardened_tool

    assert hardened["annotations"]["destructiveHint"] is True
    assert hardened["annotations"]["readOnlyHint"] is False


def test_compact_mode_reduces_pydantic_schema_tokens_and_depth():
    bloated_tools = [
        {
            "name": "create_render_plan",
            "description": "Provides a way to create a deterministic immutable video edit plan with bounded clips.",
            "inputSchema": {
                "title": "create_render_planArguments",
                "type": "object",
                "$defs": {
                    "ClipItem": {
                        "title": "ClipItem",
                        "type": "object",
                        "properties": {
                            "asset_id": {"title": "Asset Id", "type": "string", "description": "Asset SHA-256 id."},
                            "end": {
                                "title": "End",
                                "anyOf": [{"type": "number", "minimum": 0.1}, {"type": "null"}],
                                "default": None,
                                "description": "Specifies the end timestamp in seconds.",
                            },
                        },
                        "required": ["asset_id"],
                    }
                },
                "properties": {
                    "clips": {
                        "title": "Clips",
                        "type": "array",
                        "items": {"$ref": "#/$defs/ClipItem"},
                        "description": "Ordered clips list.",
                    },
                    "preset": {
                        "title": "Preset",
                        "type": "string",
                        "default": "landscape",
                        "description": "Specifies the output aspect preset.",
                    },
                },
                "required": ["clips"],
            },
            "outputSchema": {
                "title": "create_render_planOutput",
                "type": "object",
                "additionalProperties": True,
                "properties": {"id": {"title": "Id", "type": "string"}},
                "required": ["id"],
            },
        }
    ]

    summary = compact_mcp_tools(bloated_tools)
    assert summary["tokens_saved_per_turn"] > 0
    assert summary["token_reduction_pct"] > 20.0
    assert summary["after_grade"] == "A"
    assert summary["after_findings"] == 0

    compacted = summary["tools"][0]
    assert "title" not in compacted["inputSchema"]
    assert "$defs" not in compacted["inputSchema"]
    end_prop = compacted["inputSchema"]["properties"]["clips"]["items"]["properties"]["end"]
    assert end_prop["type"] == ["number", "null"]
    assert "anyOf" not in end_prop
