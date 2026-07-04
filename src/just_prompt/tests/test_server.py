"""
Tests for MCP server tool declaration helpers.
"""

from just_prompt import server


def test_configured_gateway_tool_uses_declarative_display_text():
    tool = server._configured_gateway_tool(
        {
            "name": "deep_research",
            "model": "custom-search-model",
            "category": "search",
            "description": "Custom search model exposed from config.",
        }
    )

    assert tool.name == "deep_research"
    assert tool.description.startswith("Custom search model exposed from config.")
    assert "query" in tool.inputSchema["properties"]
    assert "16-agent" not in tool.inputSchema["properties"]["query"]["description"]
    assert "cannot inspect local files" in tool.description


def test_chat_schema_discourages_habitual_max_tokens_caps():
    schema = server._configured_gateway_tool_schema("text")

    assert "Do not pass a small max_tokens value by habit" in (
        schema["properties"]["max_tokens"]["description"]
    )
    assert "options.timeout" in schema["properties"]["options"]["description"]
    assert "cannot inspect local files" in schema["properties"]["prompt"]["description"]
