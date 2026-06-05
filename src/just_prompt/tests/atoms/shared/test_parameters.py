"""
Tests for MCP parameter coercion helpers.
"""

import pytest

from just_prompt.atoms.shared.parameters import (
    parse_json_array_parameter,
    parse_json_object_parameter,
)


def test_parse_json_array_parameter_accepts_list_and_string():
    assert parse_json_array_parameter(["gateway:glm-4.7"], "models") == ["gateway:glm-4.7"]
    assert parse_json_array_parameter('["gateway:glm-4.7", "oc:qwen3-max"]', "models") == [
        "gateway:glm-4.7",
        "oc:qwen3-max",
    ]


def test_parse_json_array_parameter_rejects_non_strings():
    with pytest.raises(ValueError):
        parse_json_array_parameter("[1]", "models")


def test_parse_json_object_parameter_accepts_dict_and_string():
    assert parse_json_object_parameter({"temperature": 0.2}, "options") == {"temperature": 0.2}
    assert parse_json_object_parameter('{"temperature": 0.2}', "options") == {
        "temperature": 0.2
    }


def test_parse_json_object_parameter_rejects_array():
    with pytest.raises(ValueError):
        parse_json_object_parameter("[]", "options")
