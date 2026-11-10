"""
tests/test_schema_optimizer.py
==============================
Unit tests for `agentflight.schema_optimizer` (ToolSchemaOptimizer).
"""

from __future__ import annotations

from agentflight.schema_optimizer import ToolSchemaOptimizer


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
