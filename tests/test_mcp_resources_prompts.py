"""Tests for AgentFlight MCP Resources and Prompts primitives."""

from agentflight.mcp_server import AgentFlightMCPServer


def test_agentflight_mcp_initialize_capabilities():
    server = AgentFlightMCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    caps = resp["result"]["capabilities"]
    assert "tools" in caps
    assert "resources" in caps
    assert "prompts" in caps


def test_agentflight_mcp_resources_list_and_read():
    server = AgentFlightMCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
    resources = resp["result"]["resources"]
    assert len(resources) >= 2
    uris = [r["uri"] for r in resources]
    assert "agentflight://rules/catalog" in uris
    assert "agentflight://metrics/summary" in uris

    # Read rule catalog
    read_resp = server.handle_request(
        {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "agentflight://rules/catalog"}}
    )
    content = read_resp["result"]["contents"][0]
    assert content["mimeType"] == "application/json"
    assert "TS001" in content["text"]
    assert "TS010" in content["text"]

    # Read metrics summary
    read_resp2 = server.handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "agentflight://metrics/summary"}}
    )
    content2 = read_resp2["result"]["contents"][0]
    assert "cassette_replay_latency_p99_us" in content2["text"]


def test_agentflight_mcp_prompts_list_and_get():
    server = AgentFlightMCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "prompts/list"})
    prompts = resp["result"]["prompts"]
    assert len(prompts) >= 2
    names = [p["name"] for p in prompts]
    assert "lint-tool-definitions" in names
    assert "review-agent-trajectory" in names

    # Get prompt
    get_resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "prompts/get",
            "params": {"name": "lint-tool-definitions", "arguments": {"tools_json": '[{"name": "fetch"}]'}},
        }
    )
    res = get_resp["result"]
    assert len(res["messages"]) == 1
    assert "TS001-TS010" in res["messages"][0]["content"]["text"]


def test_agentflight_mcp_resource_templates_list():
    server = AgentFlightMCPServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 7, "method": "resources/templates/list"})
    assert "result" in resp
    templates = resp["result"]["resourceTemplates"]
    assert len(templates) >= 2
    uris = [t["uriTemplate"] for t in templates]
    assert "agentflight://cassettes/{cassette_id}" in uris
    assert "agentflight://traces/{trace_id}" in uris
