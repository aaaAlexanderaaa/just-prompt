"""
Command-line interface for just-prompt.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple

from dotenv import load_dotenv

from .atoms.shared.data_types import ModelProviders
from .atoms.shared.model_defaults import (
    apply_config_env_defaults,
    configured_model_categories,
    defaults_for_model,
    load_app_config,
    normalize_model_id,
)
from .atoms.shared.parameters import parse_json_object_parameter
from .atoms.shared.utils import DEFAULT_MODEL, split_provider_and_model
from .atoms.shared.validator import print_provider_availability
from .molecules import ask_model as ask_model_module
from .molecules import gateway_model_tools
from .server import serve

CATEGORY_TEXT = "text"
CATEGORY_SPEECH = "speech"
CATEGORY_IMAGE = "image"
CATEGORY_SEARCH = "search"
CATEGORIES = (CATEGORY_TEXT, CATEGORY_SPEECH, CATEGORY_IMAGE, CATEGORY_SEARCH)

DEFAULT_MODEL_CATEGORY_MAP = {
    "mimo-v2.5-tts": CATEGORY_SPEECH,
    "minimax-speech-2.8-turbo": CATEGORY_SPEECH,
    "minimax-m3:free": CATEGORY_TEXT,
    "gpt-image-2": CATEGORY_IMAGE,
    "grok-4.20-multi-agent-xhigh": CATEGORY_SEARCH,
}

class DefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    pass


def model_category_map() -> Dict[str, str]:
    mapping = {
        normalize_model_id(model): category
        for model, category in DEFAULT_MODEL_CATEGORY_MAP.items()
    }
    mapping.update(configured_model_categories())
    return mapping


def _known_provider(model: str) -> Optional[ModelProviders]:
    if ":" not in model:
        return None
    prefix, _ = split_provider_and_model(model)
    return ModelProviders.from_name(prefix)


def _gateway_model_id(model: str) -> str:
    provider = _known_provider(model)
    if provider and provider.full_name == "gateway":
        _, model_name = split_provider_and_model(model)
        return normalize_model_id(model_name)
    return normalize_model_id(model)


def infer_model_category(model: str) -> str:
    return model_category_map().get(_gateway_model_id(model), CATEGORY_TEXT)


def resolve_model_category(model: str, explicit_category: Optional[str]) -> Tuple[str, str]:
    if explicit_category:
        if explicit_category not in CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
        return explicit_category, "explicit"

    category = infer_model_category(model)
    source = "mapped" if _gateway_model_id(model) in model_category_map() else "default"
    return category, source


def _parse_call_prefix(argv: Sequence[str]) -> Tuple[Optional[str], Optional[str], List[str]]:
    model: Optional[str] = None
    category: Optional[str] = None
    remaining: List[str] = []
    index = 0

    while index < len(argv):
        token = argv[index]
        if token == "--category":
            if index + 1 >= len(argv):
                raise ValueError("--category requires a value")
            category = argv[index + 1]
            index += 2
            continue
        if token.startswith("--category="):
            category = token.split("=", 1)[1]
            index += 1
            continue
        if model is None and not token.startswith("-"):
            model = token
            index += 1
            continue
        remaining.append(token)
        index += 1

    return model, category, remaining


def _json_object(value: Optional[str], name: str) -> Dict[str, Any]:
    return parse_json_object_parameter(value, name)


def _options_from_args(args: argparse.Namespace, *, include_media_download: bool = False) -> Dict[str, Any]:
    options = _json_object(getattr(args, "options", None), "options")
    for key in ("api_key", "base_url", "timeout"):
        value = getattr(args, key, None)
        if value is not None:
            options[key] = value
    if include_media_download:
        media_timeout = getattr(args, "media_download_timeout", None)
        if media_timeout is not None:
            options["media_download_timeout"] = media_timeout
    return options


def _payload_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return _json_object(getattr(args, "payload", None), "payload")


def _read_text_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8")


def _stdin_text() -> Optional[str]:
    if sys.stdin.isatty():
        return None
    value = sys.stdin.read()
    return value if value else None


def _primary_input(
    args: argparse.Namespace,
    *,
    option_name: str,
    file_option_name: str,
    label: str,
) -> str:
    option_value = getattr(args, option_name, None)
    file_value = getattr(args, file_option_name, None)
    positional_parts = getattr(args, "input", None) or []
    positional_value = " ".join(positional_parts).strip() if positional_parts else None

    provided = sum(
        1
        for value in (option_value, file_value, positional_value)
        if value is not None and value != ""
    )
    if provided > 1:
        raise ValueError(
            f"provide {label} only once: positional input, --{option_name.replace('_', '-')}, "
            f"or --{file_option_name.replace('_', '-')}"
        )
    if file_value:
        return _read_text_file(file_value)
    if option_value is not None:
        return option_value
    if positional_value:
        return positional_value

    stdin_value = _stdin_text()
    if stdin_value is not None:
        return stdin_value
    raise ValueError(f"{label} is required")


def _set_file_root(args: argparse.Namespace) -> None:
    file_root = getattr(args, "file_access_root", None)
    if file_root:
        os.environ["JUST_PROMPT_FILE_ROOT"] = file_root


def _add_common_gateway_args(parser: argparse.ArgumentParser, *, default_timeout: float) -> None:
    parser.add_argument(
        "--base-url",
        default=None,
        help="Gateway base URL override. Omit to use just-prompt.config.json or MODEL_GATEWAY_BASE_URL.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gateway API key override. Prefer MODEL_GATEWAY_API_KEY for secrets.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Gateway request timeout in seconds.",
    )
    parser.add_argument(
        "--payload",
        default=None,
        help="JSON object merged into the adapter request payload.",
    )
    parser.add_argument(
        "--options",
        default=None,
        help="JSON object merged into gateway call options before named CLI options.",
    )
    parser.add_argument(
        "--file-access-root",
        default=None,
        help="Directory root for generated media paths.",
    )


def _add_sampling_args(parser: argparse.ArgumentParser, defaults: Dict[str, Any]) -> None:
    parser.add_argument("--system-prompt", default=None, help="Optional system prompt.")
    parser.add_argument(
        "--system-prompt-file",
        default=None,
        help="Read the system prompt from a UTF-8 text file.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=defaults.get("temperature"),
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=defaults.get("max_tokens"),
        help="Hard output-length cap. Omit for normal full-answer behavior.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=defaults.get("top_p"),
        help="Nucleus sampling value.",
    )


def _system_prompt(args: argparse.Namespace) -> Optional[str]:
    if args.system_prompt and args.system_prompt_file:
        raise ValueError("provide only one of --system-prompt or --system-prompt-file")
    if args.system_prompt_file:
        return _read_text_file(args.system_prompt_file)
    return args.system_prompt


def _build_text_parser(
    model: str,
    category_source: str,
    defaults: Dict[str, Any],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"just-prompt call {model}",
        description=(
            f"Call model '{model}' with the text adapter "
            f"(category source: {category_source})."
        ),
        formatter_class=DefaultsHelpFormatter,
    )
    parser.add_argument("input", nargs="*", help="Prompt text. Quote it, pass --prompt, or pipe stdin.")
    parser.add_argument("--prompt", default=None, help="Prompt text.")
    parser.add_argument("--prompt-file", default=None, help="Read prompt from a UTF-8 text file.")
    _add_sampling_args(parser, defaults)
    _add_common_gateway_args(parser, default_timeout=float(defaults.get("timeout", 300.0)))
    return parser


def _build_speech_parser(
    model: str,
    category_source: str,
    defaults: Dict[str, Any],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"just-prompt call {model}",
        description=(
            f"Call model '{model}' with the speech adapter "
            f"(category source: {category_source})."
        ),
        formatter_class=DefaultsHelpFormatter,
    )
    parser.add_argument("input", nargs="*", help="Text to synthesize. Quote it, pass --text, or pipe stdin.")
    parser.add_argument("--text", default=None, help="Text to synthesize.")
    parser.add_argument("--text-file", default=None, help="Read text from a UTF-8 text file.")
    parser.add_argument(
        "--output-path",
        default=defaults.get("output_path"),
        help="Audio file path or output directory.",
    )
    parser.add_argument(
        "--voice-id",
        default=defaults.get("voice_id", gateway_model_tools.DEFAULT_VOICE_ID),
        help="Voice ID.",
    )
    parser.add_argument("--speed", type=float, default=defaults.get("speed", 1.0), help="Voice speed.")
    parser.add_argument("--volume", type=float, default=defaults.get("volume", 1.0), help="Voice volume.")
    parser.add_argument("--pitch", type=int, default=defaults.get("pitch", 0), help="Voice pitch.")
    parser.add_argument("--sample-rate", type=int, default=defaults.get("sample_rate", 32000), help="Audio sample rate.")
    parser.add_argument("--bitrate", type=int, default=defaults.get("bitrate", 128000), help="Audio bitrate.")
    parser.add_argument("--audio-format", default=defaults.get("audio_format", "mp3"), help="Audio format.")
    parser.add_argument("--channel", type=int, default=defaults.get("channel", 1), help="Audio channel count.")
    parser.add_argument("--language-boost", default=defaults.get("language_boost"), help="MiniMax language_boost value.")
    parser.add_argument("--emotion", default=defaults.get("emotion"), help="MiniMax voice emotion.")
    parser.add_argument(
        "--subtitle-enable",
        action=argparse.BooleanOptionalAction,
        default=defaults.get("subtitle_enable", False),
        help="Request subtitle data.",
    )
    parser.add_argument(
        "--protocol",
        default=defaults.get("protocol", "auto"),
        help="Speech protocol: auto, openai:chat-completions, openai:audio-speech, or minimax:t2a_v2.",
    )
    parser.add_argument(
        "--media-download-timeout",
        type=float,
        default=float(defaults.get("media_download_timeout", 120.0)),
        help="Timeout for downloading URL media responses.",
    )
    _add_common_gateway_args(parser, default_timeout=float(defaults.get("timeout", 300.0)))
    return parser


def _build_image_parser(
    model: str,
    category_source: str,
    defaults: Dict[str, Any],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"just-prompt call {model}",
        description=(
            f"Call model '{model}' with the image adapter "
            f"(category source: {category_source})."
        ),
        formatter_class=DefaultsHelpFormatter,
    )
    parser.add_argument("input", nargs="*", help="Image prompt. Quote it, pass --prompt, or pipe stdin.")
    parser.add_argument("--prompt", default=None, help="Image prompt.")
    parser.add_argument("--prompt-file", default=None, help="Read prompt from a UTF-8 text file.")
    parser.add_argument(
        "--output-path",
        default=defaults.get("output_path"),
        help="Image file path or output directory.",
    )
    parser.add_argument("--size", default=defaults.get("size", "auto"), help="Image size.")
    parser.add_argument("--quality", default=defaults.get("quality", "auto"), help="Image quality.")
    parser.add_argument("--n", type=int, default=defaults.get("n", 1), help="Number of images.")
    parser.add_argument("--background", default=defaults.get("background"), help="Background setting.")
    parser.add_argument("--moderation", default=defaults.get("moderation"), help="Moderation setting.")
    parser.add_argument("--output-format", default=defaults.get("output_format", "png"), help="Output format.")
    parser.add_argument("--output-compression", type=int, default=defaults.get("output_compression"), help="Output compression.")
    parser.add_argument(
        "--media-download-timeout",
        type=float,
        default=float(defaults.get("media_download_timeout", 120.0)),
        help="Timeout for downloading URL media responses.",
    )
    _add_common_gateway_args(parser, default_timeout=float(defaults.get("timeout", 900.0)))
    return parser


def _build_search_parser(
    model: str,
    category_source: str,
    defaults: Dict[str, Any],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"just-prompt call {model}",
        description=(
            f"Call model '{model}' with the search adapter "
            f"(category source: {category_source})."
        ),
        formatter_class=DefaultsHelpFormatter,
    )
    parser.add_argument("input", nargs="*", help="Search query. Quote it, pass --query, or pipe stdin.")
    parser.add_argument("--query", default=None, help="Search query.")
    parser.add_argument("--query-file", default=None, help="Read query from a UTF-8 text file.")
    _add_sampling_args(parser, defaults)
    parser.add_argument(
        "--search-parameters",
        default=(
            json.dumps(defaults["search_parameters"], ensure_ascii=False)
            if isinstance(defaults.get("search_parameters"), dict)
            else None
        ),
        help="Provider-specific search parameters as a JSON object.",
    )
    _add_common_gateway_args(parser, default_timeout=float(defaults.get("timeout", 1200.0)))
    return parser


def _build_adapter_parser(
    category: str,
    *,
    model: str,
    category_source: str,
    defaults: Dict[str, Any],
) -> argparse.ArgumentParser:
    if category == CATEGORY_TEXT:
        return _build_text_parser(model, category_source, defaults)
    if category == CATEGORY_SPEECH:
        return _build_speech_parser(model, category_source, defaults)
    if category == CATEGORY_IMAGE:
        return _build_image_parser(model, category_source, defaults)
    if category == CATEGORY_SEARCH:
        return _build_search_parser(model, category_source, defaults)
    raise ValueError(f"Unsupported category: {category}")


def _call_text_adapter(model: str, args: argparse.Namespace) -> str:
    prompt = _primary_input(
        args,
        option_name="prompt",
        file_option_name="prompt_file",
        label="prompt",
    )
    _set_file_root(args)
    payload = _payload_from_args(args)
    options = _options_from_args(args)
    system_prompt = _system_prompt(args)
    provider = _known_provider(model)

    if provider and provider.full_name != "gateway":
        if system_prompt or payload:
            raise ValueError(
                "system prompts and raw payload overrides are only supported by the gateway text adapter"
            )
        for key in ("temperature", "max_tokens", "top_p"):
            value = getattr(args, key)
            if value is not None:
                options[key] = value
        return ask_model_module.ask_model(model, prompt, options=options or None)

    return gateway_model_tools.ask_gateway_chat_model(
        _gateway_model_id(model),
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_p=args.top_p,
        payload=payload,
        options=options,
    )


def _call_speech_adapter(model: str, args: argparse.Namespace) -> str:
    text = _primary_input(args, option_name="text", file_option_name="text_file", label="text")
    _set_file_root(args)
    payload = _payload_from_args(args)
    options = _options_from_args(args, include_media_download=True)
    options["protocol"] = args.protocol
    return gateway_model_tools.generate_minimax_tts(
        _gateway_model_id(model),
        text=text,
        voice_id=args.voice_id,
        output_path=args.output_path,
        speed=args.speed,
        volume=args.volume,
        pitch=args.pitch,
        sample_rate=args.sample_rate,
        bitrate=args.bitrate,
        audio_format=args.audio_format,
        channel=args.channel,
        language_boost=args.language_boost,
        emotion=args.emotion,
        subtitle_enable=args.subtitle_enable,
        payload=payload,
        options=options,
    )


def _call_image_adapter(model: str, args: argparse.Namespace) -> str:
    prompt = _primary_input(
        args,
        option_name="prompt",
        file_option_name="prompt_file",
        label="prompt",
    )
    _set_file_root(args)
    return gateway_model_tools.generate_openai_image(
        _gateway_model_id(model),
        prompt=prompt,
        output_path=args.output_path,
        size=args.size,
        quality=args.quality,
        n=args.n,
        background=args.background,
        moderation=args.moderation,
        output_format=args.output_format,
        output_compression=args.output_compression,
        payload=_payload_from_args(args),
        options=_options_from_args(args, include_media_download=True),
    )


def _call_search_adapter(model: str, args: argparse.Namespace) -> str:
    query = _primary_input(args, option_name="query", file_option_name="query_file", label="query")
    _set_file_root(args)
    return gateway_model_tools.ask_gateway_search_model(
        _gateway_model_id(model),
        query=query,
        system_prompt=_system_prompt(args),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_p=args.top_p,
        search_parameters=_json_object(args.search_parameters, "search_parameters"),
        payload=_payload_from_args(args),
        options=_options_from_args(args),
    )


def _call_adapter(category: str, model: str, args: argparse.Namespace) -> str:
    if category == CATEGORY_TEXT:
        return _call_text_adapter(model, args)
    if category == CATEGORY_SPEECH:
        return _call_speech_adapter(model, args)
    if category == CATEGORY_IMAGE:
        return _call_image_adapter(model, args)
    if category == CATEGORY_SEARCH:
        return _call_search_adapter(model, args)
    raise ValueError(f"Unsupported category: {category}")


def _print_call_overview(stdout: TextIO) -> None:
    mapped = "\n".join(
        f"  {model}: {category}"
        for model, category in sorted(model_category_map().items())
        if "-" in model or ":" in model
    )
    print(
        f"""usage: just-prompt call MODEL [--category {{{','.join(CATEGORIES)}}}] [adapter options] [input]

Call one model directly from the shell. The adapter is selected from --category,
known model mappings, or defaults to text.

Examples:
  just-prompt call minimax-m3:free "Give me three naming ideas."
  just-prompt call gpt-image-2 --help
  just-prompt call gpt-image-2 "A crisp square home lab illustration, no text."
  just-prompt call mimo-v2.5-tts --text "Read this in a calm narration voice."
  just-prompt call some-model --category image --help

Known model category mappings:
{mapped}
""",
        file=stdout,
    )


def run_call(
    argv: Sequence[str],
    *,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        if not argv or argv[0] in {"-h", "--help"}:
            _print_call_overview(stdout)
            return 0

        model, explicit_category, remaining = _parse_call_prefix(argv)
        if model is None:
            _print_call_overview(stdout)
            return 0

        category, category_source = resolve_model_category(model, explicit_category)
        defaults = defaults_for_model(_gateway_model_id(model), category)
        parser = _build_adapter_parser(
            category,
            model=model,
            category_source=category_source,
            defaults=defaults,
        )
        if any(token in {"-h", "--help"} for token in remaining):
            parser.print_help(file=stdout)
            print(
                f"\nresolved category: {category} ({category_source})",
                file=stdout,
            )
            return 0

        args = parser.parse_args(remaining)
        result = _call_adapter(category, model, args)
        print(result, file=stdout)
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=stderr)
        return 2


def _build_server_parser(prog: str) -> argparse.ArgumentParser:
    config = load_app_config()
    configured_default_models = config.get("default_models")
    default_models = (
        configured_default_models
        if isinstance(configured_default_models, str) and configured_default_models.strip()
        else DEFAULT_MODEL
    )
    parser = argparse.ArgumentParser(
        prog=prog,
        description="just-prompt - A lightweight MCP server for various LLM providers",
        epilog="Use 'just-prompt call --help' for direct one-shot CLI model calls.",
        formatter_class=DefaultsHelpFormatter,
    )
    parser.add_argument(
        "--default-models",
        default=default_models,
        help="Comma-separated list of default models to use for prompts and model name correction, in format provider:model",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--show-providers",
        action="store_true",
        help="Show available providers and exit",
    )
    parser.add_argument(
        "--gateway-base-url",
        help="OpenAI-compatible gateway base URL, e.g. https://gateway.example.com/v1",
    )
    parser.add_argument(
        "--gateway-api-key",
        help="API key for the configured model gateway. Prefer environment variables for secrets.",
    )
    parser.add_argument(
        "--file-access-root",
        help="Directory root for prompt_from_file* and ceo_and_board file access; defaults to the current working directory",
    )
    return parser


def run_server(argv: Sequence[str], *, prog: str = "just-prompt") -> int:
    parser = _build_server_parser(prog)
    args = parser.parse_args(argv)

    import logging

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.gateway_base_url:
        os.environ["MODEL_GATEWAY_BASE_URL"] = args.gateway_base_url
    if args.gateway_api_key:
        os.environ["MODEL_GATEWAY_API_KEY"] = args.gateway_api_key
    if args.file_access_root:
        os.environ["JUST_PROMPT_FILE_ROOT"] = args.file_access_root

    if args.show_providers:
        print_provider_availability()
        return 0

    asyncio.run(serve(args.default_models))
    return 0


def run(
    argv: Optional[Sequence[str]] = None,
    *,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    load_dotenv()
    apply_config_env_defaults()
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "call":
        return run_call(argv[1:], stdout=stdout, stderr=stderr)
    if argv and argv[0] == "serve":
        return run_server(argv[1:], prog="just-prompt serve")
    return run_server(argv)


def main() -> None:
    sys.exit(run())
