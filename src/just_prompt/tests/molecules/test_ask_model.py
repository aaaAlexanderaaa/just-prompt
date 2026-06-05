"""
Tests for the single-model gateway helper.
"""

import just_prompt.molecules.ask_model as ask_model_module


def test_ask_model_routes_unprefixed_models_to_gateway_prompt(monkeypatch):
    calls = []

    def fake_prompt(text, model, options=None):
        calls.append((text, model, options))
        return "ok"

    monkeypatch.setattr(ask_model_module.gateway, "prompt", fake_prompt)

    response = ask_model_module.ask_model(
        "glm-4.7",
        "hello",
        options={"protocol": "auto", "temperature": 0},
    )

    assert response == "ok"
    assert calls == [("hello", "glm-4.7", {"protocol": "auto", "temperature": 0})]


def test_ask_model_routes_gateway_prefix_to_gateway_prompt(monkeypatch):
    calls = []

    def fake_prompt(text, model, options=None):
        calls.append((text, model, options))
        return "ok"

    monkeypatch.setattr(ask_model_module.gateway, "prompt", fake_prompt)

    response = ask_model_module.ask_model("gw:qwen3-max", "hello")

    assert response == "ok"
    assert calls == [("hello", "qwen3-max", None)]
