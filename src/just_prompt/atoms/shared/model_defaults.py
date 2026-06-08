"""
Shared just-prompt application configuration.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


CONFIG_FILE_ENV = "JUST_PROMPT_CONFIG_FILE"
CONFIG_JSON_ENV = "JUST_PROMPT_CONFIG"
CONFIG_FILE_NAME = "just-prompt.config.json"

MODEL_ID_ALIASES = {
    "mimo_v2_5_tts": "mimo-v2.5-tts",
    "minimax_speech_2_8_turbo": "minimax-speech-2.8-turbo",
    "minimax_m3_free": "minimax-m3:free",
    "gpt_image_2": "gpt-image-2",
    "grok_4_20_multi_agent_xhigh": "grok-4.20-multi-agent-xhigh",
}


def normalize_model_id(model: str) -> str:
    return MODEL_ID_ALIASES.get(model, model)


def _merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
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


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"just-prompt config file must contain a JSON object: {path}")
    return data


def load_app_config() -> Dict[str, Any]:
    """
    Load non-secret app config from the project file, optional file override,
    and env JSON.
    """
    config: Dict[str, Any] = {}

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


def load_model_defaults_config() -> Dict[str, Any]:
    """
    Return the model_defaults section from shared app config.
    """
    config = load_app_config()
    model_defaults = config.get("model_defaults")
    if isinstance(model_defaults, dict):
        return model_defaults

    return {}


def app_env_defaults(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Return environment variable defaults derived from non-secret app config.
    """
    config = load_app_config() if config is None else config
    gateway = config.get("gateway")
    env: Dict[str, str] = {}
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


def apply_config_env_defaults(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Apply non-secret config values to env only when the env var is absent.
    """
    for key, value in app_env_defaults(config).items():
        if key not in os.environ:
            os.environ[key] = value


def configured_model_categories(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
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


def _named_section(config: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


def defaults_for_model(
    model: str,
    category: str,
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return merged category and model defaults.
    """
    config = load_model_defaults_config() if config is None else config
    categories = _named_section(config, "categories")
    models = _named_section(config, "models")
    normalized_model = normalize_model_id(model)

    defaults: Dict[str, Any] = {}
    category_defaults = categories.get(category)
    if isinstance(category_defaults, dict):
        defaults = _merge_dicts(defaults, category_defaults)

    model_defaults = models.get(normalized_model)
    if isinstance(model_defaults, dict):
        defaults = _merge_dicts(defaults, model_defaults)

    return defaults
