"""
Shared just-prompt application configuration.
"""

import json
import os
from pathlib import Path
from typing import Any

CONFIG_FILE_ENV = "JUST_PROMPT_CONFIG_FILE"
CONFIG_JSON_ENV = "JUST_PROMPT_CONFIG"
CONFIG_FILE_NAME = "just-prompt.config.json"
GATEWAY_MODEL_TOOLS_CONFIG_KEY = "gateway_model_tools"
GATEWAY_MODEL_TOOL_CATEGORIES = {"text", "speech", "image", "search"}

MODEL_ID_ALIASES = {
    "mimo_v2_5_tts": "mimo-v2.5-tts",
    "minimax_speech_2_8_turbo": "minimax-speech-2.8-turbo",
    "minimax_m3_free": "minimax-m3:free",
    "gpt_image_2": "gpt-image-2",
    "grok_4_20_multi_agent_xhigh": "grok-4.20-multi-agent-xhigh",
}


def normalize_model_id(model: str) -> str:
    return MODEL_ID_ALIASES.get(model, model)


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"just-prompt config file must contain a JSON object: {path}")
    return data


def load_app_config() -> dict[str, Any]:
    """
    Load non-secret app config from the project file, optional file override,
    and env JSON.
    """
    config: dict[str, Any] = {}

    default_path = Path(CONFIG_FILE_NAME)
    if default_path.exists():
        config = _merge_dicts(config, _read_json_file(default_path))

    configured_path = os.environ.get(CONFIG_FILE_ENV)
    if configured_path and configured_path.strip():
        config = _merge_dicts(
            config,
            _read_json_file(Path(configured_path).expanduser()),
        )

    inline_json = os.environ.get(CONFIG_JSON_ENV)
    if inline_json and inline_json.strip():
        inline_data = json.loads(inline_json)
        if not isinstance(inline_data, dict):
            raise ValueError(f"{CONFIG_JSON_ENV} must contain a JSON object")
        config = _merge_dicts(config, inline_data)

    return config


def load_model_defaults_config() -> dict[str, Any]:
    """
    Return the model_defaults section from shared app config.
    """
    config = load_app_config()
    model_defaults = config.get("model_defaults")
    if isinstance(model_defaults, dict):
        return model_defaults

    return {}


def app_env_defaults(config: dict[str, Any] | None = None) -> dict[str, str]:
    """
    Return environment variable defaults derived from non-secret app config.
    """
    config = load_app_config() if config is None else config
    gateway = config.get("gateway")
    env: dict[str, str] = {}
    if isinstance(gateway, dict):
        key_map = {
            "base_url": "MODEL_GATEWAY_BASE_URL",
            "protocol_base_url": "MODEL_GATEWAY_PROTOCOL_BASE_URL",
        }
        for config_key, env_key in key_map.items():
            value = gateway.get(config_key)
            if isinstance(value, str) and value.strip():
                env[env_key] = value.strip()

    file_access_root = config.get("file_access_root")
    if isinstance(file_access_root, str) and file_access_root.strip():
        env["JUST_PROMPT_FILE_ROOT"] = file_access_root.strip()

    return env


def apply_config_env_defaults(config: dict[str, Any] | None = None) -> None:
    """
    Apply non-secret config values to env only when the env var is absent.
    """
    for key, value in app_env_defaults(config).items():
        if key not in os.environ:
            os.environ[key] = value


def configured_model_categories(config: dict[str, Any] | None = None) -> dict[str, str]:
    """
    Return user-configured model -> category mappings.
    """
    config = load_app_config() if config is None else config
    categories = config.get("model_categories")
    if not isinstance(categories, dict):
        return {}
    return {
        normalize_model_id(model): category
        for model, category in categories.items()
        if isinstance(model, str) and isinstance(category, str)
    }


def _config_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _gateway_model_tool_entries(raw_tools: Any) -> list[dict[str, Any]]:
    if raw_tools is None:
        return []
    if isinstance(raw_tools, dict):
        entries = []
        for name, raw_tool in raw_tools.items():
            if not isinstance(raw_tool, dict):
                raise ValueError(
                    f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}.{name} must be a JSON object"
                )
            entries.append({**raw_tool, "name": name})
        return entries
    if isinstance(raw_tools, list):
        return raw_tools
    raise ValueError(f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY} must be a list or object")


def configured_gateway_model_tools(
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Return enabled declarative MCP tools for configured gateway models.
    """
    config = load_app_config() if config is None else config
    raw_tools = config.get(GATEWAY_MODEL_TOOLS_CONFIG_KEY)
    tools: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for index, raw_tool in enumerate(_gateway_model_tool_entries(raw_tools)):
        if not isinstance(raw_tool, dict):
            raise ValueError(
                f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}[{index}] must be a JSON object"
            )
        if not _config_bool(raw_tool.get("enabled"), default=True):
            continue

        name = raw_tool.get("name")
        model = raw_tool.get("model")
        category = raw_tool.get("category")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}[{index}].name is required")
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}.{name}.model is required")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}.{name}.category is required")

        normalized_name = name.strip()
        normalized_category = category.strip().lower()
        if normalized_name in seen_names:
            raise ValueError(f"duplicate gateway model tool name: {normalized_name}")
        if normalized_category not in GATEWAY_MODEL_TOOL_CATEGORIES:
            raise ValueError(
                f"{GATEWAY_MODEL_TOOLS_CONFIG_KEY}.{normalized_name}.category must be one "
                f"of: {', '.join(sorted(GATEWAY_MODEL_TOOL_CATEGORIES))}"
            )

        normalized_model = normalize_model_id(model.strip())
        description = raw_tool.get("description")
        if not isinstance(description, str) or not description.strip():
            description = f"Call gateway {normalized_category} model {normalized_model}."

        tool = dict(raw_tool)
        tool.update(
            {
                "name": normalized_name,
                "model": normalized_model,
                "category": normalized_category,
                "description": description.strip(),
            }
        )
        tools.append(tool)
        seen_names.add(normalized_name)

    return tools


def configured_gateway_model_categories(
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Return model -> category mappings implied by declarative gateway tools.
    """
    return {
        tool["model"]: tool["category"]
        for tool in configured_gateway_model_tools(config)
    }


def _named_section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


def defaults_for_model(
    model: str,
    category: str,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return merged category and model defaults.
    """
    config = load_model_defaults_config() if config is None else config
    categories = _named_section(config, "categories")
    models = _named_section(config, "models")
    normalized_model = normalize_model_id(model)

    defaults: dict[str, Any] = {}
    category_defaults = categories.get(category)
    if isinstance(category_defaults, dict):
        defaults = _merge_dicts(defaults, category_defaults)

    model_defaults = models.get(normalized_model)
    if isinstance(model_defaults, dict):
        defaults = _merge_dicts(defaults, model_defaults)

    return defaults
