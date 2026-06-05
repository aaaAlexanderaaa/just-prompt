"""
Generic OpenAI-compatible gateway provider.

Set MODEL_GATEWAY_BASE_URL and MODEL_GATEWAY_API_KEY to point it at any
gateway that implements the supported protocol endpoints below.
"""

import json
import logging
import os
from collections.abc import Iterable
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY_ENV_NAMES = (
    "MODEL_GATEWAY_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_API_KEY",
)

CHAT_BASE_URL_ENV_NAMES = (
    "MODEL_GATEWAY_BASE_URL",
    "OPENAI_COMPATIBLE_BASE_URL",
    "OPENAI_BASE_URL",
)

PROTOCOL_BASE_URL_ENV_NAMES = (
    "MODEL_GATEWAY_PROTOCOL_BASE_URL",
    "OPENAI_COMPATIBLE_PROTOCOL_BASE_URL",
)

PROTOCOL_ENDPOINTS: Dict[str, Tuple[str, str, Dict[str, str]]] = {
    "openai:chat-completions": ("POST", "/v1/chat/completions", {}),
    "openai:image-generations": ("POST", "/v1/images/generations", {}),
    "openai:embeddings": ("POST", "/v1/embeddings", {}),
    "anthropic:messages": ("POST", "/v1/messages", {"anthropic-version": "2023-06-01"}),
    "gemini:generate-content": ("POST", "/v1beta/models/{model}:generateContent", {}),
    "ark:image-generations": ("POST", "/ark/v3/images/generations", {}),
    "zai:layout-parsing": ("POST", "/zai/v4/layout_parsing", {}),
    "vidu:img2video": ("POST", "/vidu/v2/img2video", {}),
    "vidu:reference2video": ("POST", "/vidu/v2/reference2video", {}),
    "vidu:start-end2video": ("POST", "/vidu/v2/start-end2video", {}),
    "vidu:text2video": ("POST", "/vidu/v2/text2video", {}),
    "seedance:generations": ("POST", "/ark/v3/generations/tasks", {}),
    "minimax:t2a_v2": ("POST", "/minimax/v1/t2a_v2", {}),
    "happyhorse:video-synthesis": (
        "POST",
        "/alibaba/happyhorse/v1/video-synthesis",
        {"X-DashScope-Async": "enable"},
    ),
    "bocha:web-search": ("POST", "/bocha/v1/web-search", {}),
    "unifuncs:web-search": ("POST", "/unifuncs/web-search", {}),
    "unifuncs:web-reader": ("POST", "/unifuncs/web-reader", {}),
}

PROTOCOL_MODEL_LOCATIONS: Dict[str, str] = {
    "openai:chat-completions": "body",
    "openai:image-generations": "body",
    "openai:embeddings": "body",
    "anthropic:messages": "body",
    "gemini:generate-content": "path",
    "ark:image-generations": "body",
    "zai:layout-parsing": "body",
    "vidu:img2video": "body",
    "vidu:reference2video": "body",
    "vidu:start-end2video": "body",
    "vidu:text2video": "body",
    "seedance:generations": "body",
    "minimax:t2a_v2": "body",
    "happyhorse:video-synthesis": "body",
    "bocha:web-search": "none",
    "unifuncs:web-search": "none",
    "unifuncs:web-reader": "none",
}

DEFAULT_PROTOCOL_PRIORITY = (
    "openai:chat-completions",
    "anthropic:messages",
    "gemini:generate-content",
    "openai:image-generations",
    "openai:embeddings",
    "ark:image-generations",
    "seedance:generations",
    "vidu:text2video",
    "vidu:img2video",
    "vidu:reference2video",
    "vidu:start-end2video",
    "minimax:t2a_v2",
    "happyhorse:video-synthesis",
    "zai:layout-parsing",
    "bocha:web-search",
    "unifuncs:web-search",
    "unifuncs:web-reader",
)

REQUEST_OPTION_KEYS = {"api_key", "base_url", "timeout", "strict_model_protocol"}

TASK_ENDPOINTS = {
    "happyhorse:video-synthesis": "/alibaba/happyhorse/v1/tasks/{task_id}",
    "seedance:generations": "/ark/v3/generations/tasks/{task_id}",
    "vidu:img2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:reference2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:start-end2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:text2video": "/vidu/v2/tasks/{task_id}/creations",
}


def _model_id(model_record: Dict[str, Any]) -> Optional[str]:
    for key in ("id", "name", "model", "model_id"):
        value = model_record.get(key)
        if value:
            model_id = str(value)
            return model_id.replace("models/", "", 1)
    return None


def _protocol_id(protocol_record: Any) -> Optional[str]:
    if isinstance(protocol_record, str):
        return protocol_record
    if isinstance(protocol_record, dict):
        for key in ("id", "protocol", "name"):
            value = protocol_record.get(key)
            if value:
                return str(value)
    return None


def _looks_like_protocol_id(value: Any) -> bool:
    return isinstance(value, str) and ":" in value and value.strip() != ""


def _append_protocol(protocols: List[str], protocol_id: Optional[str]) -> None:
    if protocol_id and protocol_id not in protocols:
        protocols.append(protocol_id)


def _normalize_protocol_records(raw_protocols: Any) -> List[str]:
    if raw_protocols is None:
        return []
    if isinstance(raw_protocols, str):
        return [raw_protocols]
    if isinstance(raw_protocols, dict):
        protocol_id = _protocol_id(raw_protocols)
        if protocol_id:
            return [protocol_id]

        protocols: List[str] = []
        for key, value in raw_protocols.items():
            if _looks_like_protocol_id(key) and value not in (False, None):
                _append_protocol(protocols, str(key))
            for nested_protocol in _normalize_protocol_records(value):
                _append_protocol(protocols, nested_protocol)
        return protocols
    if not isinstance(raw_protocols, Iterable):
        return []

    protocols = []
    for protocol_record in raw_protocols:
        protocol_id = _protocol_id(protocol_record)
        _append_protocol(protocols, protocol_id)
    return protocols


def supported_protocols_from_record(model_record: Dict[str, Any]) -> List[str]:
    """
    Extract supported protocol IDs from a gateway model record.
    """
    raw_protocols = (
        model_record.get("supported_protocols")
        or model_record.get("supportedProtocols")
        or model_record.get("protocols")
    )
    return _normalize_protocol_records(raw_protocols)


def find_model_record(
    model: str, records: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a model metadata record by ID/name.
    """
    records = records if records is not None else list_model_details()
    normalized_model = model.replace("models/", "", 1)
    for record in records:
        record_id = _model_id(record)
        if record_id == normalized_model:
            return record
    return None


def supported_protocols_for_model(
    model: str, records: Optional[List[Dict[str, Any]]] = None
) -> List[str]:
    """
    Return the gateway-advertised protocols for a model when metadata is available.
    """
    record = find_model_record(model, records)
    return supported_protocols_from_record(record) if record else []


def unsupported_model_protocols(
    records: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, List[str]]:
    """
    Return gateway-advertised protocols that this client cannot call yet.
    """
    records = records if records is not None else list_model_details()
    unsupported: Dict[str, List[str]] = {}
    for record in records:
        model_id = _model_id(record)
        if not model_id:
            continue
        missing = [
            protocol
            for protocol in supported_protocols_from_record(record)
            if protocol not in PROTOCOL_ENDPOINTS
        ]
        if missing:
            unsupported[model_id] = missing
    return unsupported


def _option_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _model_list_base_url(configured_base_url: Optional[str] = None) -> str:
    if configured_base_url:
        base = configured_base_url.rstrip("/")
        if base.endswith("/v1"):
            return base
        return f"{base}/v1"
    return chat_base_url()


def _protocol_request_base_url(configured_base_url: Optional[str] = None) -> str:
    if configured_base_url:
        base = configured_base_url.rstrip("/")
        if base.endswith("/v1"):
            return base[:-3]
        return base
    return protocol_base_url()


def _safe_model_details(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 120.0,
) -> Optional[List[Dict[str, Any]]]:
    try:
        return list_model_details(api_key=api_key, base_url=base_url, timeout=timeout)
    except Exception as exc:
        logger.debug("Gateway model metadata unavailable: %s", exc)
        return None


def _model_details_for_selection(
    *,
    protocol: str,
    strict_model_protocol: bool,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 120.0,
) -> Optional[List[Dict[str, Any]]]:
    if protocol == "auto":
        if strict_model_protocol:
            return list_model_details(api_key=api_key, base_url=base_url, timeout=timeout)
        return _safe_model_details(api_key=api_key, base_url=base_url, timeout=timeout)

    if strict_model_protocol:
        return _safe_model_details(api_key=api_key, base_url=base_url, timeout=timeout)

    return None


def select_protocol_for_model(
    model: str,
    preferred_protocol: Optional[str] = None,
    records: Optional[List[Dict[str, Any]]] = None,
    strict_model_protocol: bool = True,
    fetch_records: bool = True,
) -> str:
    """
    Pick a protocol for a model using gateway model metadata when available.
    """
    preferred_protocol = (preferred_protocol or "auto").strip()
    if records is None and fetch_records:
        records = _model_details_for_selection(
            protocol=preferred_protocol,
            strict_model_protocol=strict_model_protocol,
        )

    if preferred_protocol and preferred_protocol != "auto":
        if preferred_protocol not in PROTOCOL_ENDPOINTS:
            supported = ", ".join(sorted(PROTOCOL_ENDPOINTS))
            raise ValueError(
                f"Unsupported protocol '{preferred_protocol}'. Supported protocols: {supported}"
            )
        if strict_model_protocol and records is not None:
            record = find_model_record(model, records)
            if record is None:
                raise ValueError(
                    f"Model '{model}' was not found in gateway model metadata. "
                    "Pass strict_model_protocol=false to skip metadata validation."
                )

            advertised_protocols = supported_protocols_from_record(record)
            if advertised_protocols and preferred_protocol not in advertised_protocols:
                advertised = ", ".join(advertised_protocols)
                raise ValueError(
                    f"Model '{model}' does not advertise protocol '{preferred_protocol}'. "
                    f"Advertised protocols: {advertised}"
                )
        return preferred_protocol

    if records is None:
        if strict_model_protocol:
            raise ValueError(
                "Cannot auto-select a gateway protocol without model metadata. "
                "Pass protocol explicitly or set strict_model_protocol=false to fall back "
                "to openai:chat-completions."
            )
        return "openai:chat-completions"

    record = find_model_record(model, records)
    if record is None:
        if strict_model_protocol:
            raise ValueError(
                f"Model '{model}' was not found in gateway model metadata. "
                "Pass protocol explicitly or set strict_model_protocol=false to fall back "
                "to openai:chat-completions."
            )
        return "openai:chat-completions"

    advertised_protocols = supported_protocols_from_record(record)
    if not advertised_protocols:
        logger.debug(
            "Falling back to openai:chat-completions for %s; model metadata "
            "does not advertise protocols",
            model,
        )
        return "openai:chat-completions"

    if advertised_protocols:
        for protocol in DEFAULT_PROTOCOL_PRIORITY:
            if protocol in advertised_protocols and protocol in PROTOCOL_ENDPOINTS:
                return protocol

        known_protocols = [
            protocol for protocol in advertised_protocols if protocol in PROTOCOL_ENDPOINTS
        ]
        if known_protocols:
            return known_protocols[0]

        advertised = ", ".join(advertised_protocols)
        if not strict_model_protocol:
            logger.debug(
                "Falling back to openai:chat-completions for %s; unsupported "
                "advertised protocols: %s",
                model,
                advertised,
            )
            return "openai:chat-completions"
        raise ValueError(
            f"Model '{model}' only advertises protocols this client cannot call yet: {advertised}"
        )

    return "openai:chat-completions"


def _request_options_from(options: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    request_options: Dict[str, Any] = {}
    payload_options: Dict[str, Any] = {}
    for key, value in options.items():
        if key in REQUEST_OPTION_KEYS:
            request_options[key] = value
        else:
            payload_options[key] = value
    return request_options, payload_options


def _apply_prompt_payload(protocol: str, request_payload: Dict[str, Any]) -> None:
    prompt_text = request_payload.pop("prompt", None)
    if prompt_text is None:
        return

    if protocol == "openai:chat-completions":
        request_payload.setdefault(
            "messages",
            [{"role": "user", "content": prompt_text}],
        )
        return
    if protocol == "anthropic:messages":
        if "messages" not in request_payload:
            request_payload["messages"] = [{"role": "user", "content": prompt_text}]
            request_payload.setdefault("max_tokens", 1024)
        return
    if protocol == "gemini:generate-content":
        request_payload.setdefault(
            "contents",
            [{"parts": [{"text": prompt_text}]}],
        )
        return
    if protocol == "openai:embeddings":
        request_payload.setdefault("input", prompt_text)
        return
    if protocol in {"bocha:web-search", "unifuncs:web-search"}:
        request_payload.setdefault("query", prompt_text)
        return
    if protocol == "unifuncs:web-reader":
        request_payload.setdefault("url", prompt_text)
        return

    request_payload.setdefault("prompt", prompt_text)


def _first_env(names: Tuple[str, ...]) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _api_key(explicit: Optional[str] = None, *, required: bool = True) -> Optional[str]:
    key = explicit or _first_env(API_KEY_ENV_NAMES)
    if required and not key:
        raise ValueError(
            "Missing model gateway API key. Set MODEL_GATEWAY_API_KEY or pass options.api_key."
        )
    return key


def _configured_base_url(env_names: Tuple[str, ...], *, kind: str) -> str:
    base_url = _first_env(env_names)
    if not base_url:
        env_text = " or ".join(env_names)
        raise ValueError(
            f"Missing model gateway {kind} base URL. Set {env_text} or pass options.base_url."
        )
    return base_url.rstrip("/")


def chat_base_url() -> str:
    return _configured_base_url(CHAT_BASE_URL_ENV_NAMES, kind="chat")


def protocol_base_url() -> str:
    configured = _first_env(PROTOCOL_BASE_URL_ENV_NAMES)
    if configured:
        return configured.rstrip("/")

    base = chat_base_url()
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _decode_response(raw: bytes) -> Any:
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def gateway_request(
    path: str,
    *,
    method: str = "POST",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 120.0,
    require_api_key: bool = True,
) -> Any:
    """
    Make a JSON request against the configured gateway.
    """
    body = None
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})

    key = _api_key(api_key, required=require_api_key)
    if key:
        request_headers["Authorization"] = f"Bearer {key}"

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    url = _join_url(base_url or protocol_base_url(), path)
    req = request.Request(url, data=body, headers=request_headers, method=method)

    try:
        with request.urlopen(req, timeout=timeout) as response:
            return _decode_response(response.read())
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Gateway request failed ({exc.code}) for {path}: {details}") from exc
    except error.URLError as exc:
        raise ValueError(f"Gateway request failed for {path}: {exc.reason}") from exc


def chat_completion(
    model: str,
    messages: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call an OpenAI-compatible chat completions endpoint.
    """
    options = dict(options or {})
    api_key = options.pop("api_key", None)
    base_url = options.pop("base_url", None)
    timeout = float(options.pop("timeout", 120.0))

    payload = {"model": model, "messages": messages}
    payload.update(options)

    response = gateway_request(
        "/chat/completions",
        payload=payload,
        base_url=base_url or chat_base_url(),
        api_key=api_key,
        timeout=timeout,
    )
    if not isinstance(response, dict):
        raise ValueError("Expected JSON response from chat completions")
    return response


def extract_protocol_text(response: Any, protocol: str) -> str:
    """
    Extract a text answer from text-like protocols, or JSON for structured outputs.
    """
    if not isinstance(response, dict):
        return str(response)

    if protocol == "openai:chat-completions":
        try:
            return response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return json.dumps(response, ensure_ascii=False)

    if protocol == "anthropic:messages":
        content = response.get("content")
        if isinstance(content, list):
            text_blocks = [
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if text_blocks:
                return "".join(text_blocks)
        return json.dumps(response, ensure_ascii=False)

    if protocol == "gemini:generate-content":
        candidates = response.get("candidates")
        if isinstance(candidates, list) and candidates:
            parts = (
                candidates[0]
                .get("content", {})
                .get("parts", [])
            )
            text = "".join(
                str(part.get("text", ""))
                for part in parts
                if isinstance(part, dict) and "text" in part
            )
            if text:
                return text
        return json.dumps(response, ensure_ascii=False)

    return json.dumps(response, ensure_ascii=False)


def prompt(text: str, model: str, options: Optional[Dict[str, Any]] = None) -> str:
    """
    Send a single user prompt to the configured gateway using model metadata.
    """
    options = dict(options or {})
    protocol = str(options.pop("protocol", "auto"))
    payload_override = options.pop("payload", None)
    request_options, payload_options = _request_options_from(options)
    api_key = request_options.get("api_key")
    base_url = request_options.get("base_url")
    timeout = float(request_options.get("timeout", 120.0))
    strict_model_protocol = _option_bool(
        request_options.get("strict_model_protocol"),
        True,
    )
    normalized_protocol = (protocol or "auto").strip()
    records = _model_details_for_selection(
        protocol=normalized_protocol,
        strict_model_protocol=strict_model_protocol,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )

    selected_protocol = select_protocol_for_model(
        model,
        normalized_protocol,
        records=records,
        strict_model_protocol=strict_model_protocol,
        fetch_records=False,
    )
    payload = {"prompt": text}
    payload.update(payload_options)
    if isinstance(payload_override, dict):
        payload.update(payload_override)

    call_options = dict(request_options)
    call_options["strict_model_protocol"] = False
    response = call_protocol(
        model,
        selected_protocol,
        payload=payload,
        options=call_options,
    )
    return extract_protocol_text(response, selected_protocol)


def call_protocol(
    model: str,
    protocol: str,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Call one of the documented gateway protocol endpoints.
    """
    options = dict(options or {})
    api_key = options.pop("api_key", None)
    base_url = options.pop("base_url", None)
    timeout = float(options.pop("timeout", 120.0))
    strict_model_protocol = _option_bool(options.pop("strict_model_protocol", None), True)
    normalized_protocol = (protocol or "auto").strip()
    records = _model_details_for_selection(
        protocol=normalized_protocol,
        strict_model_protocol=strict_model_protocol,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )
    protocol = select_protocol_for_model(
        model,
        normalized_protocol,
        records=records,
        strict_model_protocol=strict_model_protocol,
        fetch_records=False,
    )

    if protocol not in PROTOCOL_ENDPOINTS:
        supported = ", ".join(sorted(PROTOCOL_ENDPOINTS))
        raise ValueError(f"Unsupported protocol '{protocol}'. Supported protocols: {supported}")

    method, path, headers = PROTOCOL_ENDPOINTS[protocol]
    request_payload = dict(payload or {})

    _apply_prompt_payload(protocol, request_payload)

    model_location = PROTOCOL_MODEL_LOCATIONS.get(protocol, "body")
    if model_location == "path":
        path = path.format(model=model)
    elif model_location == "body":
        request_payload.setdefault("model", model)
    elif "{model}" in path:
        path = path.format(model=model)

    return gateway_request(
        path,
        method=method,
        payload=request_payload,
        headers=headers,
        base_url=_protocol_request_base_url(base_url),
        api_key=api_key,
        timeout=timeout,
    )


def get_task(protocol: str, task_id: str, options: Optional[Dict[str, Any]] = None) -> Any:
    """
    Poll an async protocol task when the protocol publishes a task endpoint.
    """
    if protocol not in TASK_ENDPOINTS:
        supported = ", ".join(sorted(TASK_ENDPOINTS))
        raise ValueError(f"No task endpoint for protocol '{protocol}'. Supported: {supported}")

    options = dict(options or {})
    api_key = options.pop("api_key", None)
    base_url = options.pop("base_url", None)
    timeout = float(options.pop("timeout", 120.0))

    return gateway_request(
        TASK_ENDPOINTS[protocol].format(task_id=task_id),
        method="GET",
        payload=None,
        base_url=_protocol_request_base_url(base_url),
        api_key=api_key,
        timeout=timeout,
    )


def list_model_details(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 120.0,
) -> List[Dict[str, Any]]:
    """
    Return the gateway's full model records.
    """
    response = gateway_request(
        "/models",
        method="GET",
        payload=None,
        base_url=_model_list_base_url(base_url),
        api_key=api_key,
        timeout=timeout,
        require_api_key=False,
    )
    if isinstance(response, dict):
        data = response.get("data", response.get("models", []))
        if isinstance(data, list):
            return data
    if isinstance(response, list):
        return response
    raise ValueError(f"Unexpected models response: {response}")


def list_models() -> List[str]:
    """
    Return model IDs from the configured gateway.
    """
    return [
        model_id
        for model_id in (_model_id(model_record) for model_record in list_model_details())
        if model_id
    ]
