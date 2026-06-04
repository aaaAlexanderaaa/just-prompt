"""
Tests for the generic gateway provider.
"""

from just_prompt.atoms.llm_providers import gateway


def test_call_protocol_converts_prompt_to_openai_messages(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"ok": True}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.call_protocol(
        "glm-4.7",
        "openai:chat-completions",
        payload={"prompt": "hello"},
    )

    assert response == {"ok": True}
    assert calls["path"] == "/v1/chat/completions"
    assert calls["payload"] == {
        "model": "glm-4.7",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_call_protocol_embeds_gemini_model_in_path(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"ok": True}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    gateway.call_protocol(
        "gemini-2.5-pro",
        "gemini:generate-content",
        payload={"prompt": "hello"},
    )

    assert calls["path"] == "/v1beta/models/gemini-2.5-pro:generateContent"
    assert calls["payload"] == {"contents": [{"parts": [{"text": "hello"}]}]}


def test_list_models_from_gateway_records(monkeypatch):
    monkeypatch.setattr(
        gateway,
        "gateway_request",
        lambda *args, **kwargs: {"data": [{"id": "glm-4.7"}, {"id": "qwen3-max"}]},
    )

    assert gateway.list_models() == ["glm-4.7", "qwen3-max"]
