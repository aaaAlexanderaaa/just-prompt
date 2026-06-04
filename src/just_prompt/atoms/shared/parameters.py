"""
Helpers for coercing MCP arguments into the shapes the server expects.
"""

import json
from typing import Any, Dict, List, Optional


def parse_json_array_parameter(value: Any, name: str) -> Optional[List[str]]:
    """
    Accept a real JSON array or a stringified JSON array from MCP clients.
    """
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must be a list or JSON array string") from exc

    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")

    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must contain only strings")

    return value


def parse_json_object_parameter(value: Any, name: str) -> Dict[str, Any]:
    """
    Accept a real JSON object or a stringified JSON object from MCP clients.
    """
    if value is None:
        return {}

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must be an object or JSON object string") from exc

    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")

    return value
