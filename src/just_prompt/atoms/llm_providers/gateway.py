"""
Generic OpenAI-compatible gateway provider.

The defaults target TokenDance, but the provider is intentionally generic:
set MODEL_GATEWAY_BASE_URL and MODEL_GATEWAY_API_KEY to point it at any
OpenAI-compatible model gateway.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_CHAT_BASE_URL = "https://tokendance.space/gateway/v1"
DEFAULT_PROTOCOL_BASE_URL = "https://tokendance.space/gateway"

API_KEY_ENV_NAMES = (
    "MODEL_GATEWAY_API_KEY",
    "TOKENDANCE_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_API_KEY",
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
    "unifuncs:web-search": ("POST", "/unifuncs/web-search", {}),
    "unifuncs:web-reader": ("POST", "/unifuncs/web-reader", {}),
}

TASK_ENDPOINTS = {
    "happyhorse:video-synthesis": "/alibaba/happyhorse/v1/tasks/{task_id}",
    "seedance:generations": "/ark/v3/generations/tasks/{task_id}",
    "vidu:img2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:reference2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:start-end2video": "/vidu/v2/tasks/{task_id}/creations",
    "vidu:text2video": "/vidu/v2/tasks/{task_id}/creations",
}


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
            "Missing model gateway API key. Set MODEL_GATEWAY_API_KEY or TOKENDANCE_API_KEY."
        )
    return key


def chat_base_url() -> str:
    return (
        os.environ.get("MODEL_GATEWAY_BASE_URL")
        or os.environ.get("TOKENDANCE_BASE_URL")
        or os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or DEFAULT_CHAT_BASE_URL
    ).rstrip("/")


def protocol_base_url() -> str:
    configured = os.environ.get("MODEL_GATEWAY_PROTOCOL_BASE_URL") or os.environ.get(
        "TOKENDANCE_GATEWAY_BASE_URL"
    )
    if configured:
        return configured.rstrip("/")

    base = chat_base_url()
    if base.endswith("/v1"):
        return base[:-3]
    return base or DEFAULT_PROTOCOL_BASE_URL


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


def prompt(text: str, model: str) -> str:
    """
    Send a single user prompt to the configured OpenAI-compatible gateway.
    """
    response = chat_completion(model, [{"role": "user", "content": text}])
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected chat completion response: {response}") from exc
    return content or ""


def call_protocol(
    model: str,
    protocol: str,
    payload: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Call one of TokenDance's documented protocol endpoints.
    """
    if protocol not in PROTOCOL_ENDPOINTS:
        supported = ", ".join(sorted(PROTOCOL_ENDPOINTS))
        raise ValueError(f"Unsupported protocol '{protocol}'. Supported protocols: {supported}")

    options = dict(options or {})
    api_key = options.pop("api_key", None)
    base_url = options.pop("base_url", None)
    timeout = float(options.pop("timeout", 120.0))

    method, path, headers = PROTOCOL_ENDPOINTS[protocol]
    request_payload = dict(payload or {})

    prompt_text = request_payload.pop("prompt", None)
    if protocol == "openai:chat-completions" and prompt_text and "messages" not in request_payload:
        request_payload["messages"] = [{"role": "user", "content": prompt_text}]
    elif protocol == "anthropic:messages" and prompt_text and "messages" not in request_payload:
        request_payload["messages"] = [{"role": "user", "content": prompt_text}]
        request_payload.setdefault("max_tokens", 1024)
    elif protocol == "gemini:generate-content" and prompt_text and "contents" not in request_payload:
        request_payload["contents"] = [{"parts": [{"text": prompt_text}]}]

    if protocol == "gemini:generate-content":
        path = path.format(model=model)
    else:
        request_payload.setdefault("model", model)

    return gateway_request(
        path,
        method=method,
        payload=request_payload,
        headers=headers,
        base_url=base_url or protocol_base_url(),
        api_key=api_key,
        timeout=timeout,
    )


def get_task(protocol: str, task_id: str, options: Optional[Dict[str, Any]] = None) -> Any:
    """
    Poll an async protocol task when TokenDance documents a task endpoint.
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
        base_url=base_url or protocol_base_url(),
        api_key=api_key,
        timeout=timeout,
    )


def list_model_details() -> List[Dict[str, Any]]:
    """
    Return the gateway's full model records.
    """
    response = gateway_request(
        "/models",
        method="GET",
        payload=None,
        base_url=chat_base_url(),
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
    return [str(model["id"]) for model in list_model_details() if "id" in model]
