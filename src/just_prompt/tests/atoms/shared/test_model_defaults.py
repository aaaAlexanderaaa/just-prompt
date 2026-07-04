"""
Tests for model/category default argument loading.
"""

import json
from pathlib import Path

from just_prompt.atoms.shared import model_defaults


def test_defaults_for_model_merges_category_and_model_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("just-prompt.config.json").write_text(
        json.dumps(
            {
                "model_defaults": {
                    "categories": {
                        "image": {
                            "size": "4k",
                            "quality": "auto",
                        }
                    },
                    "models": {
                        "gpt-image-2": {
                            "quality": "high",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    defaults = model_defaults.defaults_for_model("gpt_image_2", "image")

    assert defaults == {
        "size": "4k",
        "quality": "high",
    }


def test_inline_env_defaults_override_file_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        model_defaults.CONFIG_JSON_ENV,
        json.dumps({"model_defaults": {"categories": {"image": {"size": "8k"}}}}),
    )
    Path("just-prompt.config.json").write_text(
        json.dumps({"model_defaults": {"categories": {"image": {"size": "4k"}}}}),
        encoding="utf-8",
    )

    defaults = model_defaults.defaults_for_model("any-image-model", "image")

    assert defaults["size"] == "8k"


def test_app_env_defaults_from_shared_config():
    env = model_defaults.app_env_defaults(
        {
            "gateway": {"base_url": "https://gateway.example.test/v1"},
            "file_access_root": "/tmp/just-prompt-files",
        }
    )

    assert env == {
        "MODEL_GATEWAY_BASE_URL": "https://gateway.example.test/v1",
        "JUST_PROMPT_FILE_ROOT": "/tmp/just-prompt-files",
    }


def test_configured_model_categories_normalizes_aliases():
    categories = model_defaults.configured_model_categories(
        {"model_categories": {"gpt_image_2": "image"}}
    )

    assert categories == {"gpt-image-2": "image"}


def test_configured_gateway_model_tools_normalizes_and_skips_disabled():
    tools = model_defaults.configured_gateway_model_tools(
        {
            "gateway_model_tools": [
                {
                    "name": "deep_research",
                    "model": "grok_4_20_multi_agent_xhigh",
                    "category": "SEARCH",
                    "description": "  Search deeply.  ",
                },
                {
                    "name": "hidden_tool",
                    "model": "hidden-model",
                    "category": "text",
                    "enabled": False,
                },
            ]
        }
    )

    assert tools == [
        {
            "name": "deep_research",
            "model": "grok-4.20-multi-agent-xhigh",
            "category": "search",
            "description": "Search deeply.",
        }
    ]


def test_configured_gateway_model_tools_accepts_object_form():
    tools = model_defaults.configured_gateway_model_tools(
        {
            "gateway_model_tools": {
                "image_tool": {
                    "model": "gpt-image-2",
                    "category": "image",
                }
            }
        }
    )

    assert tools == [
        {
            "name": "image_tool",
            "model": "gpt-image-2",
            "category": "image",
            "description": "Call gateway image model gpt-image-2.",
        }
    ]


def test_configured_gateway_model_categories_from_tool_declarations():
    categories = model_defaults.configured_gateway_model_categories(
        {
            "gateway_model_tools": [
                {
                    "name": "search_tool",
                    "model": "grok-4.20-multi-agent-xhigh",
                    "category": "search",
                }
            ]
        }
    )

    assert categories == {"grok-4.20-multi-agent-xhigh": "search"}
