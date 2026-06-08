"""
Fixed-model tools for selected gateway models.
"""

import base64
import binascii
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

from ..atoms.llm_providers import gateway
from ..atoms.shared.file_access import configured_file_root, resolve_checked_path
from ..atoms.shared.model_defaults import defaults_for_model

MIMO_V2_5_TTS_MODEL = "mimo-v2.5-tts"
MINIMAX_SPEECH_2_8_TURBO_MODEL = "minimax-speech-2.8-turbo"
MINIMAX_M3_FREE_MODEL = "minimax-m3:free"
GPT_IMAGE_2_MODEL = "gpt-image-2"
GROK_4_20_MULTI_AGENT_XHIGH_MODEL = "grok-4.20-multi-agent-xhigh"

MINIMAX_TTS_PROTOCOL = "minimax:t2a_v2"
OPENAI_CHAT_PROTOCOL = "openai:chat-completions"
OPENAI_IMAGE_PROTOCOL = "openai:image-generations"
OPENAI_AUDIO_SPEECH_PROTOCOL = "openai:audio-speech"

DEFAULT_VOICE_ID = "male-qn-qingse"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_output_filename(prefix: str, suffix: str) -> str:
    return f"{prefix}-{_utc_stamp()}{suffix}"


def _default_output_path(prefix: str, suffix: str) -> Path:
    return configured_file_root() / "generated" / _default_output_filename(prefix, suffix)


def _output_path(output_path: Optional[str], prefix: str, suffix: str) -> Path:
    if output_path and output_path.strip():
        raw_path = output_path.strip()
        path = Path(raw_path)
        directory_hint = raw_path.endswith(("/", "\\"))
    else:
        path = _default_output_path(prefix, suffix)
        directory_hint = False

    resolved = resolve_checked_path(str(path), must_exist=False)
    if directory_hint or (resolved.exists() and resolved.is_dir()):
        resolved = resolve_checked_path(
            str(resolved / _default_output_filename(prefix, suffix)),
            must_exist=False,
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _numbered_path(path: Path, index: int) -> Path:
    if index == 0:
        return path
    return path.with_name(f"{path.stem}-{index + 1}{path.suffix}")


def _safe_suffix(value: Optional[str], default: str) -> str:
    normalized = (value or default).strip().lower().lstrip(".")
    suffix_map = {
        "jpg": "jpg",
        "jpeg": "jpg",
        "mp3": "mp3",
        "opus": "opus",
        "pcm": "pcm",
        "png": "png",
        "wav": "wav",
        "webp": "webp",
    }
    return f".{suffix_map.get(normalized, default)}"


def _decode_data_string(value: str) -> Optional[bytes]:
    stripped = value.strip()
    if not stripped or stripped.startswith(("http://", "https://")):
        return None

    if "," in stripped and stripped.lower().startswith("data:"):
        stripped = stripped.split(",", 1)[1]

    hex_candidate = stripped.replace("\n", "").replace(" ", "")
    if len(hex_candidate) % 2 == 0:
        try:
            return bytes.fromhex(hex_candidate)
        except ValueError:
            pass

    try:
        return base64.b64decode(stripped, validate=True)
    except binascii.Error:
        return None


def _download_media_url(url: str, *, timeout: float) -> bytes:
    req = request.Request(
        url,
        headers={"User-Agent": "just-prompt-mcp/1.0"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            data = response.read()
    except error.HTTPError as exc:
        raise ValueError(f"Media URL download failed ({exc.code}) for {url}") from exc
    except error.URLError as exc:
        raise ValueError(f"Media URL download failed for {url}: {exc.reason}") from exc

    if not data:
        raise ValueError(f"Media URL download returned an empty file for {url}")
    return data


def _find_audio_value(response: Any) -> Optional[str]:
    if not isinstance(response, dict):
        return None

    candidates = [
        response.get("audio"),
        response.get("audio_data"),
        response.get("b64_json"),
    ]
    data = response.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("audio"),
                data.get("audio_data"),
                data.get("b64_json"),
                data.get("url"),
            ]
        )
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict):
                audio = message.get("audio")
                if isinstance(audio, dict):
                    candidates.extend(
                        [
                            audio.get("data"),
                            audio.get("b64_json"),
                            audio.get("url"),
                        ]
                    )

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def _redact_large_media(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, nested in value.items():
            if key in {"audio", "audio_data", "b64_json"} and isinstance(nested, str):
                redacted[key] = f"<media len={len(nested)}>"
            else:
                redacted[key] = _redact_large_media(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_large_media(item) for item in value]
    return value


def _media_result_text(result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def _summarize_audio_response(
    response: Any,
    *,
    output_path: Optional[str],
    prefix: str,
    audio_format: str,
    media_download_timeout: float,
) -> str:
    if isinstance(response, bytes):
        path = _output_path(output_path, prefix, _safe_suffix(audio_format, "mp3"))
        path.write_bytes(response)
        return _media_result_text(
            {
                "saved_audio_path": str(path),
                "saved_audio_bytes": len(response),
                "model_response_type": "bytes",
            }
        )

    audio_value = _find_audio_value(response)
    if not audio_value:
        result = {"model_response": _redact_large_media(response)}
        raise ValueError(
            "No audio field was found in the gateway response: "
            f"{json.dumps(result, ensure_ascii=False)[:1000]}"
        )

    if audio_value.startswith(("http://", "https://")):
        audio_bytes = _download_media_url(
            audio_value,
            timeout=media_download_timeout,
        )
        path = _output_path(output_path, prefix, _safe_suffix(audio_format, "mp3"))
        path.write_bytes(audio_bytes)
        return _media_result_text(
            {
                "saved_audio_path": str(path),
                "saved_audio_bytes": len(audio_bytes),
                "source_audio_url": audio_value,
            }
        )

    audio_bytes = _decode_data_string(audio_value)
    if audio_bytes is None:
        raise ValueError("Audio field was not hex or base64 encoded.")

    path = _output_path(output_path, prefix, _safe_suffix(audio_format, "mp3"))
    path.write_bytes(audio_bytes)
    return _media_result_text(
        {
            "saved_audio_path": str(path),
            "saved_audio_bytes": len(audio_bytes),
        }
    )


def _image_records(response: Any) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _summarize_image_response(
    response: Any,
    *,
    output_path: Optional[str],
    prefix: str,
    output_format: str,
    media_download_timeout: float,
) -> str:
    result: Dict[str, Any] = {}
    records = _image_records(response)
    if not records:
        result["warning"] = "No image data records were found in the gateway response."
        result["model_response"] = _redact_large_media(response)
        return _media_result_text(result)

    saved_paths = []
    saved_bytes = []
    urls = []
    suffix = _safe_suffix(output_format, "png")
    base_path = _output_path(output_path, prefix, suffix)

    for index, record in enumerate(records):
        url = record.get("url")
        if isinstance(url, str) and url:
            image_bytes = _download_media_url(
                url,
                timeout=media_download_timeout,
            )
        else:
            encoded = record.get("b64_json") or record.get("image") or record.get("data")
            if not isinstance(encoded, str):
                continue
            image_bytes = _decode_data_string(encoded)
            if image_bytes is None:
                continue

        if isinstance(url, str) and url:
            urls.append(url)

        path = _numbered_path(base_path, index)
        path.write_bytes(image_bytes)
        saved_paths.append(str(path))
        saved_bytes.append(len(image_bytes))

    if saved_paths:
        result["saved_image_paths"] = saved_paths
        result["saved_image_bytes"] = saved_bytes
    if urls:
        result["source_image_urls"] = urls
    if not saved_paths:
        result["warning"] = "Image records did not include url or decodable b64_json fields."
        result["model_response"] = _redact_large_media(response)
    return _media_result_text(result)


def _gateway_call_options(options: Optional[Dict[str, Any]], default_timeout: float) -> Dict[str, Any]:
    call_options = dict(options or {})
    call_options.setdefault("timeout", default_timeout)
    call_options["strict_model_protocol"] = False
    return call_options


def _merge_payload(base_payload: Dict[str, Any], payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base_payload)
    if payload:
        merged.update(payload)
    return merged


def _defaulted(value: Any, defaults: Dict[str, Any], key: str, fallback: Any) -> Any:
    return value if value is not None else defaults.get(key, fallback)


def generate_minimax_tts(
    model: str,
    *,
    text: str,
    voice_id: Optional[str] = None,
    output_path: Optional[str] = None,
    speed: Optional[float] = None,
    volume: Optional[float] = None,
    pitch: Optional[int] = None,
    sample_rate: Optional[int] = None,
    bitrate: Optional[int] = None,
    audio_format: Optional[str] = None,
    channel: Optional[int] = None,
    language_boost: Optional[str] = None,
    emotion: Optional[str] = None,
    subtitle_enable: Optional[bool] = None,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate speech through the configured gateway.
    """
    defaults = defaults_for_model(model, "speech")
    voice_id = _defaulted(voice_id, defaults, "voice_id", DEFAULT_VOICE_ID)
    speed = float(_defaulted(speed, defaults, "speed", 1.0))
    volume = float(_defaulted(volume, defaults, "volume", 1.0))
    pitch = int(_defaulted(pitch, defaults, "pitch", 0))
    sample_rate = int(_defaulted(sample_rate, defaults, "sample_rate", 32000))
    bitrate = int(_defaulted(bitrate, defaults, "bitrate", 128000))
    audio_format = str(_defaulted(audio_format, defaults, "audio_format", "mp3"))
    channel = int(_defaulted(channel, defaults, "channel", 1))
    language_boost = _defaulted(language_boost, defaults, "language_boost", None)
    emotion = _defaulted(emotion, defaults, "emotion", None)
    subtitle_enable = bool(_defaulted(subtitle_enable, defaults, "subtitle_enable", False))
    output_path = _defaulted(output_path, defaults, "output_path", None)

    options = dict(options or {})
    protocol = str(options.pop("protocol", "auto"))
    media_download_timeout = float(options.pop("media_download_timeout", 120.0))

    if protocol == "auto":
        protocol = OPENAI_CHAT_PROTOCOL

    if protocol == OPENAI_CHAT_PROTOCOL:
        request_payload = {
            "model": model,
            "messages": [{"role": "assistant", "content": text}],
            "stream": False,
        }
    elif protocol == OPENAI_AUDIO_SPEECH_PROTOCOL:
        request_payload: Dict[str, Any] = {
            "model": model,
            "input": text,
            "voice": voice_id,
            "response_format": audio_format,
        }
        if speed != 1.0:
            request_payload["speed"] = speed
    else:
        voice_setting: Dict[str, Any] = {
            "voice_id": voice_id,
            "speed": speed,
            "vol": volume,
            "pitch": pitch,
        }
        if emotion:
            voice_setting["emotion"] = emotion

        request_payload = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": voice_setting,
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "format": audio_format,
                "channel": channel,
            },
            "subtitle_enable": subtitle_enable,
        }
        if language_boost:
            request_payload["language_boost"] = language_boost

    response = gateway.call_protocol(
        model,
        protocol,
        payload=_merge_payload(request_payload, payload),
        options=_gateway_call_options(options, default_timeout=300.0),
    )
    return _summarize_audio_response(
        response,
        output_path=output_path,
        prefix=model.replace(":", "-"),
        audio_format=audio_format,
        media_download_timeout=media_download_timeout,
    )


def generate_mimo_v2_5_tts(**kwargs: Any) -> str:
    return generate_minimax_tts(MIMO_V2_5_TTS_MODEL, **kwargs)


def generate_minimax_speech_2_8_turbo(**kwargs: Any) -> str:
    return generate_minimax_tts(MINIMAX_SPEECH_2_8_TURBO_MODEL, **kwargs)


def ask_gateway_chat_model(
    model: str,
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
    default_timeout: float = 300.0,
    defaults_category: str = "text",
) -> str:
    """
    Ask an OpenAI chat-completions compatible gateway model.
    """
    defaults = defaults_for_model(model, defaults_category)
    temperature = _defaulted(temperature, defaults, "temperature", None)
    max_tokens = _defaulted(max_tokens, defaults, "max_tokens", None)
    top_p = _defaulted(top_p, defaults, "top_p", None)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    request_payload: Dict[str, Any] = {"messages": messages, "stream": False}
    if temperature is not None:
        request_payload["temperature"] = temperature
    if max_tokens is not None:
        request_payload["max_tokens"] = max_tokens
    if top_p is not None:
        request_payload["top_p"] = top_p

    response = gateway.call_protocol(
        model,
        OPENAI_CHAT_PROTOCOL,
        payload=_merge_payload(request_payload, payload),
        options=_gateway_call_options(options, default_timeout=default_timeout),
    )
    return gateway.extract_protocol_text(response, OPENAI_CHAT_PROTOCOL)


def ask_minimax_m3_free(**kwargs: Any) -> str:
    return ask_gateway_chat_model(MINIMAX_M3_FREE_MODEL, **kwargs)


def generate_openai_image(
    model: str,
    *,
    prompt: str,
    output_path: Optional[str] = None,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    n: Optional[int] = None,
    background: Optional[str] = None,
    moderation: Optional[str] = None,
    output_format: Optional[str] = None,
    output_compression: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    defaults = defaults_for_model(model, "image")
    size = str(_defaulted(size, defaults, "size", "auto"))
    quality = str(_defaulted(quality, defaults, "quality", "auto"))
    n = int(_defaulted(n, defaults, "n", 1))
    background = _defaulted(background, defaults, "background", None)
    moderation = _defaulted(moderation, defaults, "moderation", None)
    output_format = str(_defaulted(output_format, defaults, "output_format", "png"))
    output_compression = _defaulted(
        output_compression,
        defaults,
        "output_compression",
        None,
    )
    output_path = _defaulted(output_path, defaults, "output_path", None)

    options = dict(options or {})
    media_download_timeout = float(options.pop("media_download_timeout", 120.0))

    request_payload: Dict[str, Any] = {
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    if quality:
        request_payload["quality"] = quality
    if background:
        request_payload["background"] = background
    if moderation:
        request_payload["moderation"] = moderation
    if output_format:
        request_payload["output_format"] = output_format
    if output_compression is not None:
        request_payload["output_compression"] = output_compression

    response = gateway.call_protocol(
        model,
        OPENAI_IMAGE_PROTOCOL,
        payload=_merge_payload(request_payload, payload),
        options=_gateway_call_options(options, default_timeout=900.0),
    )
    return _summarize_image_response(
        response,
        output_path=output_path,
        prefix=model.replace(":", "-"),
        output_format=output_format,
        media_download_timeout=media_download_timeout,
    )


def generate_gpt_image_2(**kwargs: Any) -> str:
    return generate_openai_image(GPT_IMAGE_2_MODEL, **kwargs)


def ask_gateway_search_model(
    model: str,
    *,
    query: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    search_parameters: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
    default_timeout: float = 1200.0,
) -> str:
    defaults = defaults_for_model(model, "search")
    temperature = _defaulted(temperature, defaults, "temperature", None)
    max_tokens = _defaulted(max_tokens, defaults, "max_tokens", None)
    top_p = _defaulted(top_p, defaults, "top_p", None)
    search_parameters = _defaulted(search_parameters, defaults, "search_parameters", None)

    request_payload: Dict[str, Any] = {}
    if search_parameters:
        request_payload["search_parameters"] = search_parameters

    return ask_gateway_chat_model(
        model,
        prompt=query,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        payload=_merge_payload(request_payload, payload),
        options=options,
        default_timeout=default_timeout,
        defaults_category="search",
    )


def ask_grok_4_20_multi_agent_xhigh(
    *,
    query: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    search_parameters: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    return ask_gateway_search_model(
        GROK_4_20_MULTI_AGENT_XHIGH_MODEL,
        query=query,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        search_parameters=search_parameters,
        payload=payload,
        options=options,
    )
