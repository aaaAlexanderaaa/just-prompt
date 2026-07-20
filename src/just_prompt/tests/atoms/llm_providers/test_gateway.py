"""
Tests for the generic gateway provider.
"""

import json
import os

import pytest

from just_prompt.atoms.llm_providers import gateway


@pytest.fixture(autouse=True)
def configured_gateway(monkeypatch):
    if not os.environ.get("MODEL_GATEWAY_BASE_URL"):
        monkeypatch.setenv("MODEL_GATEWAY_BASE_URL", "https://gateway.example.com/v1")
    if not os.environ.get("MODEL_GATEWAY_API_KEY"):
        monkeypatch.setenv("MODEL_GATEWAY_API_KEY", "test-key")


TOKENDANCE_DOCUMENTED_PROTOCOLS = {
    "openai:chat-completions",
    "openai:image-generations",
    "anthropic:messages",
    "gemini:generate-content",
    "openai:embeddings",
    "zai:layout-parsing",
    "ark:image-generations",
    "vidu:text2video",
    "vidu:img2video",
    "vidu:reference2video",
    "vidu:start-end2video",
    "seedance:generations",
    "minimax:t2a_v2",
    "bocha:web-search",
    "happyhorse:video-synthesis",
    "unifuncs:web-search",
    "unifuncs:web-reader",
}


def test_every_protocol_declares_model_location():
    assert set(gateway.PROTOCOL_MODEL_LOCATIONS) == set(gateway.PROTOCOL_ENDPOINTS)


def test_gateway_supports_tokendance_documented_protocols():
    assert TOKENDANCE_DOCUMENTED_PROTOCOLS <= set(gateway.PROTOCOL_ENDPOINTS)


def test_gateway_supports_openai_audio_speech_protocol():
    assert gateway.PROTOCOL_ENDPOINTS["openai:audio-speech"] == (
        "POST",
        "/v1/audio/speech",
        {},
    )


def test_unsupported_model_protocols_allows_tokendance_documented_protocols():
    records = [
        {"id": protocol.replace(":", "-"), "supported_protocols": [protocol]}
        for protocol in TOKENDANCE_DOCUMENTED_PROTOCOLS
    ]

    assert gateway.unsupported_model_protocols(records) == {}


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("MODEL_GATEWAY_CONTRACT_TEST") != "1"
    or not os.environ.get("MODEL_GATEWAY_BASE_URL"),
    reason=(
        "Set MODEL_GATEWAY_CONTRACT_TEST=1 and MODEL_GATEWAY_BASE_URL to check "
        "the configured live gateway."
    ),
)
def test_configured_live_gateway_model_protocol_contract():
    records = gateway.list_model_details()

    assert gateway.unsupported_model_protocols(records) == {}


@pytest.mark.parametrize(
    ("raw_protocols", "expected"),
    [
        (
            {
                "openai:chat-completions": True,
                "anthropic:messages": False,
            },
            ["openai:chat-completions"],
        ),
        (
            {
                "chat": {"id": "openai:chat-completions"},
                "gemini": {"protocol": "gemini:generate-content"},
            },
            ["openai:chat-completions", "gemini:generate-content"],
        ),
        (
            {
                "primary": {"name": "openai:embeddings"},
                "fallback": ["anthropic:messages"],
            },
            ["openai:embeddings", "anthropic:messages"],
        ),
    ],
)
def test_supported_protocols_from_record_accepts_common_metadata_shapes(
    raw_protocols, expected
):
    assert gateway.supported_protocols_from_record(
        {"id": "model", "supported_protocols": raw_protocols}
    ) == expected


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (
            {"id": "gpt-image-2", "supported_endpoint_types": ["openai"]},
            ["openai:image-generations"],
        ),
        (
            {
                "id": "deep-research-v1",
                "supported_endpoint_types": ["openai"],
            },
            ["openai:chat-completions"],
        ),
        (
            {"id": "mimo-v2.5-tts", "supported_endpoint_types": []},
            ["openai:chat-completions", "openai:audio-speech", "minimax:t2a_v2"],
        ),
        (
            {"id": "minimax-speech-2.8-turbo", "supported_endpoint_types": []},
            ["openai:chat-completions", "openai:audio-speech", "minimax:t2a_v2"],
        ),
        (
            {"id": "minimax-m3:free", "supported_endpoint_types": []},
            ["openai:chat-completions"],
        ),
    ],
)
def test_supported_protocols_from_record_infers_gateway_endpoint_types(record, expected):
    assert gateway.supported_protocols_from_record(record) == expected


def test_call_protocol_converts_prompt_to_openai_messages(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "glm-4.7",
                        "supported_protocols": ["openai:chat-completions"],
                    }
                ]
            }
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
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "gemini-2.5-pro",
                        "supported_protocols": ["gemini:generate-content"],
                    }
                ]
            }
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


def test_anthropic_prompt_payload_uses_broad_default_max_tokens(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "claude-compatible",
                        "supported_protocols": ["anthropic:messages"],
                    }
                ]
            }
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"content": [{"type": "text", "text": "anthropic response"}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt("hello", "claude-compatible")

    assert response == "anthropic response"
    assert calls["path"] == "/v1/messages"
    assert calls["payload"]["messages"] == [{"role": "user", "content": "hello"}]
    assert calls["payload"]["max_tokens"] == 65535


def test_prompt_auto_selects_protocol_from_model_metadata(monkeypatch):
    calls = []

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "gemini-2.5-pro",
                        "supported_protocols": ["gemini:generate-content"],
                    }
                ]
            }
        calls.append((path, kwargs["payload"]))
        return {
            "candidates": [
                {"content": {"parts": [{"text": "hello from gemini"}]}}
            ]
        }

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt("hello", "gemini-2.5-pro")

    assert response == "hello from gemini"
    assert calls == [
        (
            "/v1beta/models/gemini-2.5-pro:generateContent",
            {"contents": [{"parts": [{"text": "hello"}]}]},
        )
    ]


def test_prompt_auto_falls_back_to_chat_for_id_only_model_metadata(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {"data": [{"id": "glm-4.7"}]}
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"choices": [{"message": {"content": "chat response"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt("hello", "glm-4.7")

    assert response == "chat response"
    assert calls == {
        "path": "/v1/chat/completions",
        "payload": {
            "model": "glm-4.7",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }


def test_prompt_auto_rejects_models_missing_from_metadata(monkeypatch):
    def fake_request(path, **kwargs):
        if path == "/models":
            return {"data": []}
        raise AssertionError("auto protocol selection should fail before request")

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    with pytest.raises(ValueError) as exc_info:
        gateway.prompt("hello", "missing-model")

    assert "was not found in gateway model metadata" in str(exc_info.value)


def test_prompt_auto_requires_metadata_by_default(monkeypatch):
    def fake_request(path, **kwargs):
        if path == "/models":
            raise ValueError("metadata unavailable")
        raise AssertionError("auto protocol selection should fail before request")

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    with pytest.raises(ValueError) as exc_info:
        gateway.prompt("hello", "glm-4.7")

    assert "metadata unavailable" in str(exc_info.value)


def test_prompt_auto_can_fallback_when_strict_model_protocol_is_false(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            raise ValueError("metadata unavailable")
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"choices": [{"message": {"content": "fallback response"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt(
        "hello",
        "glm-4.7",
        options={"strict_model_protocol": False},
    )

    assert response == "fallback response"
    assert calls == {
        "path": "/v1/chat/completions",
        "payload": {
            "model": "glm-4.7",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }


def test_prompt_auto_strict_false_falls_back_from_unknown_advertised_protocol(
    monkeypatch,
):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "future-model",
                        "supported_protocols": ["vendor:future-protocol"],
                    }
                ]
            }
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"choices": [{"message": {"content": "fallback response"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt(
        "hello",
        "future-model",
        options={"strict_model_protocol": False},
    )

    assert response == "fallback response"
    assert calls == {
        "path": "/v1/chat/completions",
        "payload": {
            "model": "future-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }


def test_call_protocol_rejects_protocol_not_advertised_by_model(monkeypatch):
    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "embedding-model",
                        "supported_protocols": ["openai:embeddings"],
                    }
                ]
            }
        return {"ok": True}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    with pytest.raises(ValueError) as exc_info:
        gateway.call_protocol(
            "embedding-model",
            "openai:chat-completions",
            payload={"prompt": "hello"},
        )

    assert "does not advertise protocol" in str(exc_info.value)


def test_call_protocol_strict_false_skips_protocol_metadata_check(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            raise AssertionError("strict_model_protocol=false should not fetch metadata")
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"ok": True}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.call_protocol(
        "embedding-model",
        "openai:chat-completions",
        payload={"prompt": "hello"},
        options={"strict_model_protocol": False},
    )

    assert response == {"ok": True}
    assert calls["path"] == "/v1/chat/completions"
    assert calls["payload"] == {
        "model": "embedding-model",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_call_protocol_persists_response_only_diagnostic(monkeypatch, tmp_path):
    explicit_api_key = "explicit-gateway-secret"
    response = {
        "id": "chatcmpl-test",
        "echo": f"upstream echoed {explicit_api_key}",
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": "",
                    "reasoning_content": "private model reasoning",
                    "api_key": "test-key",
                },
            }
        ],
        "usage": {"completion_tokens": 128},
    }
    monkeypatch.setattr(gateway, "gateway_request", lambda *args, **kwargs: response)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "response.json"

    returned = gateway.call_protocol(
        "kimi-k3",
        "openai:chat-completions",
        payload={"prompt": "hello"},
        options={
            "api_key": explicit_api_key,
            "strict_model_protocol": False,
            "response_output_path": str(output_path),
        },
    )

    assert returned == response
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["model"] == "kimi-k3"
    assert artifact["protocol"] == "openai:chat-completions"
    assert artifact["response"]["choices"][0]["finish_reason"] == "length"
    assert artifact["response"]["choices"][0]["message"]["reasoning_content"] == (
        "private model reasoning"
    )
    assert artifact["response"]["choices"][0]["message"]["api_key"] == "[REDACTED]"
    artifact_text = output_path.read_text(encoding="utf-8")
    assert "test-key" not in artifact_text
    assert explicit_api_key not in artifact_text
    assert artifact["response"]["echo"] == "upstream echoed [REDACTED]"
    assert output_path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("option_name", ["response_output_path", "raw_response_path"])
def test_call_protocol_confines_diagnostic_paths_to_file_root(
    monkeypatch,
    tmp_path,
    option_name,
):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    forbidden_path = tmp_path / "outside" / "response.json"
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(allowed_root))
    monkeypatch.setattr(gateway, "gateway_request", lambda *args, **kwargs: {"ok": True})

    with pytest.raises(ValueError, match="outside the configured file access root"):
        gateway.call_protocol(
            "kimi-k3",
            "openai:chat-completions",
            payload={"prompt": "hello"},
            options={
                "strict_model_protocol": False,
                option_name: str(forbidden_path),
            },
        )

    assert not forbidden_path.exists()


def test_extract_protocol_text_supports_openai_content_parts():
    response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "first"},
                        {"type": "output_text", "text": {"value": " second"}},
                        {"type": "reasoning", "text": "hidden"},
                    ]
                }
            }
        ]
    }

    assert gateway.extract_protocol_text(response, "openai:chat-completions") == "first second"


def test_extract_protocol_text_never_promotes_reasoning_to_answer():
    response = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {"content": "", "reasoning_content": "unfinished reasoning"},
            }
        ]
    }

    assert gateway.extract_protocol_text(response, "openai:chat-completions") == ""


def test_prompt_payload_override_does_not_keep_seed_prompt_with_messages(monkeypatch):
    calls = {}
    override_messages = [{"role": "user", "content": "override"}]

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "glm-4.7",
                        "supported_protocols": ["openai:chat-completions"],
                    }
                ]
            }
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"choices": [{"message": {"content": "override response"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt(
        "seed prompt",
        "glm-4.7",
        options={"payload": {"messages": override_messages}},
    )

    assert response == "override response"
    assert calls == {
        "path": "/v1/chat/completions",
        "payload": {
            "model": "glm-4.7",
            "messages": override_messages,
        },
    }


def test_prompt_uses_custom_gateway_options_for_metadata_and_request(monkeypatch):
    calls = []

    def fake_request(path, **kwargs):
        calls.append(
            {
                "path": path,
                "base_url": kwargs.get("base_url"),
                "api_key": kwargs.get("api_key"),
                "timeout": kwargs.get("timeout"),
                "payload": kwargs.get("payload"),
                "require_api_key": kwargs.get("require_api_key"),
            }
        )
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "custom-model",
                        "supported_protocols": ["openai:chat-completions"],
                    }
                ]
            }
        return {"choices": [{"message": {"content": "custom response"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.prompt(
        "hello",
        "custom-model",
        options={
            "base_url": "https://custom.example/gateway/v1",
            "api_key": "custom-key",
            "timeout": 3,
        },
    )

    assert response == "custom response"
    assert calls[0] == {
        "path": "/models",
        "base_url": "https://custom.example/gateway/v1",
        "api_key": "custom-key",
        "timeout": 3.0,
        "payload": None,
        "require_api_key": False,
    }
    assert calls[1] == {
        "path": "/v1/chat/completions",
        "base_url": "https://custom.example/gateway",
        "api_key": "custom-key",
        "timeout": 3.0,
        "payload": {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
        "require_api_key": None,
    }


def test_prompt_defaults_to_long_model_timeout(monkeypatch):
    calls = []

    def fake_request(path, **kwargs):
        calls.append({"path": path, "timeout": kwargs.get("timeout")})
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "kimi-k2.7-code",
                        "supported_protocols": ["openai:chat-completions"],
                    }
                ]
            }
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    assert gateway.prompt("hello", "kimi-k2.7-code") == "ok"
    assert calls == [
        {"path": "/models", "timeout": 900.0},
        {"path": "/v1/chat/completions", "timeout": 900.0},
    ]


def test_prompt_treats_zero_token_limits_as_uncapped(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": "glm-4.7",
                        "supported_protocols": ["openai:chat-completions"],
                    }
                ]
            }
        calls["payload"] = kwargs["payload"]
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    gateway.prompt(
        "hello",
        "glm-4.7",
        options={"max_tokens": 0, "max_completion_tokens": "0"},
    )

    assert calls["payload"] == {
        "model": "glm-4.7",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_gateway_request_timeout_error_is_actionable(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(gateway.request, "urlopen", fake_urlopen)

    with pytest.raises(TimeoutError) as exc_info:
        gateway.gateway_request("/v1/chat/completions", payload={}, timeout=7)

    message = str(exc_info.value)
    assert "timed out after 7s" in message
    assert "options.timeout" in message
    assert "gateway/model may already have received the request" in message


@pytest.mark.parametrize(
    ("model", "protocol", "expected_path"),
    [
        ("bocha-web-search", "bocha:web-search", "/bocha/v1/web-search"),
        ("unifuncs-web-search", "unifuncs:web-search", "/unifuncs/web-search"),
    ],
)
def test_call_protocol_does_not_inject_model_for_search_service_protocols(
    monkeypatch, model, protocol, expected_path
):
    calls = {}

    def fake_request(path, **kwargs):
        if path == "/models":
            return {
                "data": [
                    {
                        "id": model,
                        "supported_protocols": [protocol],
                    }
                ]
            }
        calls["path"] = path
        calls["payload"] = kwargs["payload"]
        return {"results": []}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    gateway.call_protocol(
        model,
        "auto",
        payload={"prompt": "Model Context Protocol"},
    )

    assert calls["path"] == expected_path
    assert calls["payload"] == {"query": "Model Context Protocol"}


def test_seedance_paths_follow_tokendance_quickstart_routes():
    assert gateway.PROTOCOL_ENDPOINTS["seedance:generations"] == (
        "POST",
        "/ark/v3/generations/tasks",
        {},
    )
    assert gateway.TASK_ENDPOINTS["seedance:generations"] == (
        "/ark/v3/generations/tasks/{task_id}"
    )


def test_get_task_normalizes_v1_base_url(monkeypatch):
    calls = {}

    def fake_request(path, **kwargs):
        calls["path"] = path
        calls["base_url"] = kwargs["base_url"]
        calls["method"] = kwargs["method"]
        return {"id": "task-1"}

    monkeypatch.setattr(gateway, "gateway_request", fake_request)

    response = gateway.get_task(
        "seedance:generations",
        "task-1",
        options={"base_url": "https://custom.example/gateway/v1"},
    )

    assert response == {"id": "task-1"}
    assert calls == {
        "path": "/ark/v3/generations/tasks/task-1",
        "base_url": "https://custom.example/gateway",
        "method": "GET",
    }


def test_unsupported_model_protocols_reports_advertised_gaps():
    records = [
        {"id": "known", "supported_protocols": ["openai:chat-completions"]},
        {"id": "future", "supported_protocols": ["tokendance:future-protocol"]},
    ]

    assert gateway.unsupported_model_protocols(records) == {
        "future": ["tokendance:future-protocol"]
    }


def test_list_models_from_gateway_records(monkeypatch):
    monkeypatch.setattr(
        gateway,
        "gateway_request",
        lambda *args, **kwargs: {
            "data": [
                {"id": "glm-4.7"},
                {"name": "models/gemini-2.5-pro"},
                {"model_id": "qwen3-max"},
            ]
        },
    )

    assert gateway.list_models() == ["glm-4.7", "gemini-2.5-pro", "qwen3-max"]
