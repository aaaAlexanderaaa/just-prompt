"""
Tests for fixed gateway model MCP helpers.
"""

import base64
import json
from pathlib import Path

from just_prompt.molecules import gateway_model_tools as tools


def test_minimax_speech_tool_uses_minimax_protocol_and_saves_hex_audio(
    monkeypatch, tmp_path
):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return {"data": {"audio": b"audio-bytes".hex(), "status": 2}}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "speech.mp3"

    response_text = tools.generate_minimax_speech_2_8_turbo(
        text="Describe a quiet morning in Chengdu.",
        voice_id="male-qn-qingse",
        output_path=str(output_path),
        options={"protocol": "minimax:t2a_v2"},
    )

    assert calls["model"] == "minimax-speech-2.8-turbo"
    assert calls["protocol"] == "minimax:t2a_v2"
    assert calls["payload"]["model"] == "minimax-speech-2.8-turbo"
    assert calls["payload"]["stream"] is False
    assert calls["payload"]["voice_setting"]["voice_id"] == "male-qn-qingse"
    assert calls["options"]["strict_model_protocol"] is False
    response = json.loads(response_text)
    assert output_path.read_bytes() == b"audio-bytes"
    assert response["saved_audio_path"] == str(output_path)
    assert "model_response" not in response


def test_mimo_tts_tool_uses_fixed_model(monkeypatch, tmp_path):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        return {"data": {"audio": b"mimo-audio".hex()}}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))

    tools.generate_mimo_v2_5_tts(
        text="Read one sentence with a calm documentary tone.",
        output_path=str(tmp_path / "mimo.mp3"),
        options={"protocol": "minimax:t2a_v2"},
    )

    assert calls["model"] == "mimo-v2.5-tts"
    assert calls["protocol"] == "minimax:t2a_v2"
    assert calls["payload"]["model"] == "mimo-v2.5-tts"


def test_mimo_tts_defaults_to_assistant_chat_audio(monkeypatch, tmp_path):
    calls = {}
    encoded = base64.b64encode(b"mimo-chat-audio").decode("ascii")

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "audio": {"data": encoded, "transcript": "spoken words"},
                    }
                }
            ]
        }

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "mimo-chat.mp3"

    response_text = tools.generate_mimo_v2_5_tts(
        text="Read one sentence with a calm documentary tone.",
        output_path=str(output_path),
    )

    assert calls["model"] == "mimo-v2.5-tts"
    assert calls["protocol"] == "openai:chat-completions"
    assert calls["payload"] == {
        "model": "mimo-v2.5-tts",
        "messages": [
            {
                "role": "assistant",
                "content": "Read one sentence with a calm documentary tone.",
            }
        ],
        "stream": False,
    }
    response = json.loads(response_text)
    assert output_path.read_bytes() == b"mimo-chat-audio"
    assert response["saved_audio_path"] == str(output_path)
    assert "model_response" not in response


def test_minimax_speech_defaults_to_assistant_chat_audio(monkeypatch, tmp_path):
    calls = {}
    encoded = base64.b64encode(b"minimax-chat-audio").decode("ascii")

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        return {"choices": [{"message": {"audio": {"data": encoded}}}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "minimax-chat.mp3"

    response_text = tools.generate_minimax_speech_2_8_turbo(
        text="Describe a quiet morning in Chengdu.",
        output_path=str(output_path),
    )

    assert calls["model"] == "minimax-speech-2.8-turbo"
    assert calls["protocol"] == "openai:chat-completions"
    assert calls["payload"] == {
        "model": "minimax-speech-2.8-turbo",
        "messages": [{"role": "assistant", "content": "Describe a quiet morning in Chengdu."}],
        "stream": False,
    }
    response = json.loads(response_text)
    assert output_path.read_bytes() == b"minimax-chat-audio"
    assert response["saved_audio_path"] == str(output_path)
    assert "model_response" not in response


def test_tts_tool_can_use_openai_audio_speech_and_save_binary_response(
    monkeypatch, tmp_path
):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return b"mp3-bytes"

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "speech.mp3"

    response_text = tools.generate_minimax_speech_2_8_turbo(
        text="Describe a quiet morning in Chengdu.",
        voice_id="male-qn-qingse",
        output_path=str(output_path),
        options={"protocol": "openai:audio-speech"},
    )

    assert calls["model"] == "minimax-speech-2.8-turbo"
    assert calls["protocol"] == "openai:audio-speech"
    assert calls["payload"] == {
        "model": "minimax-speech-2.8-turbo",
        "input": "Describe a quiet morning in Chengdu.",
        "voice": "male-qn-qingse",
        "response_format": "mp3",
    }
    assert output_path.read_bytes() == b"mp3-bytes"
    assert json.loads(response_text)["saved_audio_path"] == str(output_path)


def test_tts_tool_downloads_audio_url(monkeypatch, tmp_path):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        return {"data": {"url": "https://cdn.example.test/narration.mp3"}}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"downloaded-mp3"

    def fake_urlopen(req, timeout=None):
        calls["url"] = req.full_url
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setattr(tools.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "speech.mp3"

    response_text = tools.generate_mimo_v2_5_tts(
        text="Read a calm one-sentence update for a family archive.",
        output_path=str(output_path),
        options={"media_download_timeout": 7},
    )

    response = json.loads(response_text)
    assert calls == {
        "url": "https://cdn.example.test/narration.mp3",
        "timeout": 7.0,
    }
    assert "model_response" not in response
    assert output_path.read_bytes() == b"downloaded-mp3"
    assert response["saved_audio_path"] == str(output_path)
    assert response["saved_audio_bytes"] == len(b"downloaded-mp3")
    assert response["source_audio_url"] == "https://cdn.example.test/narration.mp3"


def test_tts_tool_accepts_output_directory(monkeypatch, tmp_path):
    encoded = base64.b64encode(b"directory-mp3").decode("ascii")

    def fake_call_protocol(model, protocol, payload=None, options=None):
        return {"choices": [{"message": {"audio": {"data": encoded}}}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))

    response_text = tools.generate_mimo_v2_5_tts(
        text="Read a short home archive note.",
        output_path=str(tmp_path),
    )

    response = json.loads(response_text)
    saved_path = Path(response["saved_audio_path"])
    assert saved_path.parent == tmp_path
    assert saved_path.name.startswith("mimo-v2.5-tts-")
    assert saved_path.suffix == ".mp3"
    assert saved_path.read_bytes() == b"directory-mp3"


def test_minimax_m3_free_uses_non_streaming_chat(monkeypatch):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return {"choices": [{"message": {"content": "concise answer"}}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)

    response = tools.ask_minimax_m3_free(
        prompt="Compare two useful naming schemes for a home lab index.",
        system_prompt="Answer tersely.",
        temperature=0.2,
    )

    assert response == "concise answer"
    assert calls["model"] == "minimax-m3:free"
    assert calls["protocol"] == "openai:chat-completions"
    assert calls["payload"]["stream"] is False
    assert calls["payload"]["temperature"] == 0.2
    assert calls["payload"]["messages"][0]["role"] == "system"
    assert calls["options"]["strict_model_protocol"] is False


def test_gpt_image_2_saves_base64_image(monkeypatch, tmp_path):
    calls = {}
    encoded = base64.b64encode(b"png-bytes").decode("ascii")

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))
    output_path = tmp_path / "image.png"

    response_text = tools.generate_gpt_image_2(
        prompt="A precise isometric diagram of a tiny server rack.",
        output_path=str(output_path),
        quality="high",
    )

    assert calls["model"] == "gpt-image-2"
    assert calls["protocol"] == "openai:image-generations"
    assert calls["payload"]["prompt"].startswith("A precise")
    assert calls["payload"]["quality"] == "high"
    assert calls["options"]["timeout"] == 900.0
    response = json.loads(response_text)
    assert output_path.read_bytes() == b"png-bytes"
    assert response["saved_image_paths"] == [str(output_path)]
    assert "model_response" not in response


def test_gpt_image_2_prompt_only_uses_auto_defaults_and_downloads_url(
    monkeypatch, tmp_path
):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return {"data": [{"url": "https://cdn.example.test/home-lab.png"}]}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"downloaded-png"

    def fake_urlopen(req, timeout=None):
        calls["download_url"] = req.full_url
        calls["download_timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setattr(tools.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))

    response_text = tools.generate_gpt_image_2(
        prompt="A compact labeled-free illustration of a home lab shelf.",
        options={"media_download_timeout": 9},
    )

    response = json.loads(response_text)
    saved_path = tmp_path / "generated" / Path(response["saved_image_paths"][0]).name
    assert calls["model"] == "gpt-image-2"
    assert calls["protocol"] == "openai:image-generations"
    assert calls["payload"] == {
        "prompt": "A compact labeled-free illustration of a home lab shelf.",
        "n": 1,
        "size": "4k",
        "quality": "auto",
        "output_format": "png",
    }
    assert calls["download_url"] == "https://cdn.example.test/home-lab.png"
    assert calls["download_timeout"] == 9.0
    assert Path(response["saved_image_paths"][0]) == saved_path
    assert saved_path.read_bytes() == b"downloaded-png"
    assert response["saved_image_bytes"] == [len(b"downloaded-png")]
    assert response["source_image_urls"] == ["https://cdn.example.test/home-lab.png"]
    assert "model_response" not in response


def test_gpt_image_2_accepts_output_directory(monkeypatch, tmp_path):
    encoded = base64.b64encode(b"directory-png").decode("ascii")

    def fake_call_protocol(model, protocol, payload=None, options=None):
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(tmp_path))

    response_text = tools.generate_gpt_image_2(
        prompt="A clean square home lab concept image, no text.",
        output_path=str(tmp_path),
    )

    response = json.loads(response_text)
    saved_path = Path(response["saved_image_paths"][0])
    assert saved_path.parent == tmp_path
    assert saved_path.name.startswith("gpt-image-2-")
    assert saved_path.suffix == ".png"
    assert saved_path.read_bytes() == b"directory-png"


def test_grok_search_uses_long_non_streaming_chat(monkeypatch):
    calls = {}

    def fake_call_protocol(model, protocol, payload=None, options=None):
        calls["model"] = model
        calls["protocol"] = protocol
        calls["payload"] = payload
        calls["options"] = options
        return {"choices": [{"message": {"content": "fresh synthesis"}}]}

    monkeypatch.setattr(tools.gateway, "call_protocol", fake_call_protocol)

    response = tools.ask_grok_4_20_multi_agent_xhigh(
        query="Find recent operational lessons from small Kubernetes clusters.",
        search_parameters={"mode": "auto"},
    )

    assert response == "fresh synthesis"
    assert calls["model"] == "grok-4.20-multi-agent-xhigh"
    assert calls["protocol"] == "openai:chat-completions"
    assert calls["payload"]["stream"] is False
    assert calls["payload"]["search_parameters"] == {"mode": "auto"}
    assert calls["options"]["timeout"] == 1200.0
