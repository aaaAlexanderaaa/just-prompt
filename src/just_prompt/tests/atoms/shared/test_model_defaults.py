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


def test_load_app_config_merges_local_config_fragments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("just-prompt.config.json").write_text(
        json.dumps(
            {
                "gateway_model_tools": [
                    {
                        "name": "base_chat",
                        "model": "base-chat-model",
                        "category": "text",
                    }
                ],
                "model_defaults": {
                    "categories": {
                        "search": {
                            "timeout": 1200,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    local_dir = Path(model_defaults.CONFIG_LOCAL_DIR_NAME)
    local_dir.mkdir()
    (local_dir / "01-search.json").write_text(
        json.dumps(
            {
                "gateway_model_tools": [
                    {
                        "name": "research_web",
                        "model": "search-model",
                        "category": "search",
                    }
                ],
                "model_defaults": {
                    "models": {
                        "search-model": {
                            "timeout": 1800,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (local_dir / "02-image.json").write_text(
        json.dumps(
            {
                "gateway_model_tools": {
                    "image_creator": {
                        "model": "image-model",
                        "category": "image",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = model_defaults.load_app_config()
    tools = model_defaults.configured_gateway_model_tools(config)

    assert [tool["name"] for tool in tools] == [
        "base_chat",
        "research_web",
        "image_creator",
    ]
    assert model_defaults.defaults_for_model(
        "search-model",
        "search",
        config=config["model_defaults"],
    )["timeout"] == 1800


def test_gateway_model_tools_merge_by_name_across_fragments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("just-prompt.config.json").write_text(
        json.dumps(
            {
                "gateway_model_tools": [
                    {
                        "name": "research_web",
                        "model": "search-model",
                        "category": "search",
                        "description": "Old description.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    local_dir = Path(model_defaults.CONFIG_LOCAL_DIR_NAME)
    local_dir.mkdir()
    (local_dir / "01-research-description.json").write_text(
        json.dumps(
            {
                "gateway_model_tools": [
                    {
                        "name": "research_web",
                        "description": "New description.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    tools = model_defaults.configured_gateway_model_tools()

    assert tools == [
        {
            "name": "research_web",
            "model": "search-model",
            "category": "search",
            "description": "New description.",
        }
    ]


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
                    "name": "image_tool",
                    "model": "gpt_image_2",
                    "category": "IMAGE",
                    "description": "  Generate images.  ",
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
            "name": "image_tool",
            "model": "gpt-image-2",
            "category": "image",
            "description": "Generate images.",
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
                    "model": "deep-research-v1",
                    "category": "search",
                }
            ]
        }
    )

    assert categories == {"deep-research-v1": "search"}
