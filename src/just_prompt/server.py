"""
MCP server for just-prompt.
"""

import asyncio
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from .atoms.shared.parameters import (
    parse_json_array_parameter,
    parse_json_object_parameter,
)
from .atoms.shared.utils import DEFAULT_MODEL
from .atoms.shared.validator import print_provider_availability
from .molecules.ask_model import (
    ask_model,
    call_model_protocol,
    get_model_task,
    list_gateway_model_details,
)
from .molecules.ceo_and_board_prompt import DEFAULT_CEO_MODEL, ceo_and_board_prompt
from .molecules.gateway_model_tools import (
    ask_grok_4_20_multi_agent_xhigh,
    ask_minimax_m3_free,
    generate_gpt_image_2,
    generate_mimo_v2_5_tts,
    generate_minimax_speech_2_8_turbo,
)
from .molecules.list_models import list_models as list_models_func
from .molecules.list_providers import list_providers as list_providers_func
from .molecules.prompt import prompt
from .molecules.prompt_from_file import prompt_from_file
from .molecules.prompt_from_file_to_file import prompt_from_file_to_file

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


SENSITIVE_ARGUMENT_KEYS = {
    "api_key",
    "authorization",
    "content",
    "input",
    "messages",
    "password",
    "payload",
    "prompt",
    "query",
    "secret",
    "system_prompt",
    "text",
    "token",
}

PATH_ARGUMENT_KEYS = {"abs_file_path", "abs_output_dir", "file_path", "output_dir", "output_path"}


def _summarize_for_log(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= 120 else f"<string len={len(value)}>"
    if isinstance(value, list):
        return f"<list len={len(value)}>"
    if isinstance(value, dict):
        return f"<object keys={sorted(value.keys())}>"
    return value


def _redacted_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in arguments.items():
        normalized = key.lower()
        if normalized in PATH_ARGUMENT_KEYS:
            redacted[key] = "<path redacted>"
        elif normalized == "options":
            if isinstance(value, dict):
                redacted[key] = {
                    option_key: (
                        "<redacted>"
                        if option_key.lower() in SENSITIVE_ARGUMENT_KEYS
                        or "key" in option_key.lower()
                        or "secret" in option_key.lower()
                        or "token" in option_key.lower()
                        else _summarize_for_log(option_value)
                    )
                    for option_key, option_value in value.items()
                }
            else:
                redacted[key] = "<redacted options>"
        elif (
            normalized in SENSITIVE_ARGUMENT_KEYS
            or "key" in normalized
            or "secret" in normalized
            or "token" in normalized
        ):
            redacted[key] = "<redacted>"
        else:
            redacted[key] = _summarize_for_log(value)
    return redacted


def _bool_argument(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _optional_bool_argument(value: Any) -> bool | None:
    if value is None:
        return None
    return _bool_argument(value)


def _optional_float_argument(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int_argument(value: Any) -> int | None:
    return None if value is None else int(value)


# Tool names enum
class JustPromptTools:
    ASK_MODEL = "ask_model"
    MIMO_V2_5_TTS = "mimo_v2_5_tts"
    MINIMAX_SPEECH_2_8_TURBO = "minimax_speech_2_8_turbo"
    MINIMAX_M3_FREE = "minimax_m3_free"
    GPT_IMAGE_2 = "gpt_image_2"
    GROK_4_20_MULTI_AGENT_XHIGH = "grok_4_20_multi_agent_xhigh"
    PROMPT = "prompt"
    PROMPT_FROM_FILE = "prompt_from_file"
    PROMPT_FROM_FILE_TO_FILE = "prompt_from_file_to_file"
    CEO_AND_BOARD = "ceo_and_board"
    LIST_PROVIDERS = "list_providers"
    LIST_MODELS = "list_models"
    LIST_GATEWAY_MODELS = "list_gateway_models"
    CALL_MODEL_PROTOCOL = "call_model_protocol"
    GET_MODEL_TASK = "get_model_task"

# Schema classes for MCP tools
class PromptSchema(BaseModel):
    text: str = Field(..., description="The prompt text")
    models_prefixed_by_provider: list[str] | str | None = Field(
        None,
        description="List of models with provider prefixes (e.g., 'openai:gpt-4o' or 'o:gpt-4o'). If not provided, uses default models."
    )
    error_strategy: dict[str, Any] | str | None = Field(
        None,
        description="Optional error handling object: strategy best_effort, all_or_nothing, or retry_with_backoff; max_retries; backoff_seconds.",
    )


class AskModelSchema(BaseModel):
    model: str = Field(..., description="Model ID. Unprefixed IDs are sent to the configured OpenAI-compatible gateway.")
    prompt: str = Field(..., description="Prompt text to send to the model")
    options: dict[str, Any] | str | None = Field(
        None,
        description="Optional gateway options. Use protocol='auto' to infer from model metadata, or pass a protocol ID plus payload/chat options such as temperature, max_tokens, top_p, api_key, base_url, timeout.",
    )


class GatewaySpeechSchema(BaseModel):
    text: str = Field(..., description="Text to synthesize into speech")
    voice_id: str | None = Field(None, description="Voice ID for speech protocols that accept one. Omit to use the configured default.")
    output_path: str | None = Field(None, description="Optional audio file path or output directory. Directory paths save generated/<model>-style filenames inside that directory; omitted paths default to generated/<model>-<utc>.mp3 under the configured file root.")
    speed: float | None = Field(None, description="Voice speed. Omit to use the configured default.")
    volume: float | None = Field(None, description="Voice volume; sent as MiniMax voice_setting.vol. Omit to use the configured default.")
    pitch: int | None = Field(None, description="Voice pitch. Omit to use the configured default.")
    sample_rate: int | None = Field(None, description="Audio sample rate. Omit to use the configured default.")
    bitrate: int | None = Field(None, description="Audio bitrate. Omit to use the configured default.")
    audio_format: str | None = Field(None, description="Audio format such as mp3, wav, pcm, or opus. Omit to use the configured default.")
    channel: int | None = Field(None, description="Audio channel count. Omit to use the configured default.")
    language_boost: str | None = Field(None, description="Optional MiniMax language_boost value")
    emotion: str | None = Field(None, description="Optional MiniMax voice emotion")
    subtitle_enable: bool | None = Field(None, description="Whether to request subtitle data. Omit to use the configured default.")
    payload: dict[str, Any] | str | None = Field(None, description="Optional raw payload overrides")
    options: dict[str, Any] | str | None = Field(None, description="Optional gateway call options: protocol, api_key, base_url, timeout, media_download_timeout")


class GatewayChatSchema(BaseModel):
    prompt: str = Field(..., description="Prompt text")
    system_prompt: str | None = Field(None, description="Optional system prompt")
    temperature: float | None = Field(None, description="Sampling temperature")
    max_tokens: int | None = Field(None, description="Maximum output tokens")
    top_p: float | None = Field(None, description="Nucleus sampling value")
    payload: dict[str, Any] | str | None = Field(None, description="Optional raw chat-completions payload overrides")
    options: dict[str, Any] | str | None = Field(None, description="Optional gateway call options: api_key, base_url, timeout")


class GptImage2Schema(BaseModel):
    prompt: str = Field(..., description="Image prompt")
    output_path: str | None = Field(None, description="Optional image file path or output directory. Directory paths save generated filenames inside that directory; omitted paths default to generated/gpt-image-2-<utc>.png under the configured file root.")
    size: str | None = Field(None, description="Image size. Omit to use the configured default; this project defaults image models to 4k.")
    quality: str | None = Field(None, description="Image quality. Omit to use the configured default, or pass a provider-supported explicit value when you intentionally want to override it.")
    n: int | None = Field(None, description="Number of images to generate. Omit to use the configured default.")
    background: str | None = Field(None, description="Optional background setting")
    moderation: str | None = Field(None, description="Optional moderation setting")
    output_format: str | None = Field(None, description="Output format such as png, jpeg, or webp. Omit to use the configured default.")
    output_compression: int | None = Field(None, description="Optional compression level for supported formats")
    payload: dict[str, Any] | str | None = Field(None, description="Optional raw image generation payload overrides")
    options: dict[str, Any] | str | None = Field(None, description="Optional gateway call options: api_key, base_url, timeout, media_download_timeout")


class GrokSearchSchema(BaseModel):
    query: str = Field(
        ...,
        description=(
            "Search or research question. Prefer concrete entities, dates, and desired evidence.\n"
            "\n"
            "For deep research, use this template (fill in [topic]):\n"
            "Perform a comprehensive 16-agent Realtime Multi-Agent Deep Research in xhigh mode on [topic]. Leave no stone unturned. "
            "Harper team: be exhaustive with web, X (use advanced operators for latest posts), academic papers, official reports. "
            "Benjamin: verify all technical/financial/logical claims. "
            "Lucas: ruthlessly challenge assumptions and explore contrarian scenarios. "
            "Follow strict process: decompose -> parallel research -> multiple rounds of debate -> consensus synthesis. "
            "Deliver a professional-grade report equivalent to a top consulting firm team working for days. "
            "Structure: Executive Summary, Detailed Analysis (use tables for comparisons), Counterarguments & Limitations, Actionable Insights, Complete References with links where available."
        ),
    )
    system_prompt: str | None = Field(
        None,
        description="Optional instructions for source quality, synthesis style, or output structure. Example: \"Prefer primary sources, include concrete publication dates, and separate verified facts from inference.\"",
    )
    temperature: float | None = Field(None, description="Optional sampling temperature.")
    max_tokens: int | None = Field(None, description="Optional maximum output tokens.")
    top_p: float | None = Field(None, description="Optional nucleus sampling value.")
    search_parameters: dict[str, Any] | str | None = Field(None, description="Optional provider-specific search parameters passed through to the gateway.")
    payload: dict[str, Any] | str | None = Field(None, description="Optional raw chat-completions payload overrides for just-prompt. Use only when the task requires provider-specific fields.")
    options: dict[str, Any] | str | None = Field(
        None,
        description="Optional gateway call options such as timeout, api_key, or base_url. Default timeout is 1200s; raise via options.timeout only when truly needed. Normal calls should omit this.",
    )


class PromptFromFileSchema(BaseModel):
    abs_file_path: str = Field(..., description="Absolute path to the file containing the prompt (must be an absolute path, not relative)")
    models_prefixed_by_provider: list[str] | str | None = Field(
        None,
        description="List of models with provider prefixes (e.g., 'openai:gpt-4o' or 'o:gpt-4o'). If not provided, uses default models."
    )
    error_strategy: dict[str, Any] | str | None = Field(None, description="Optional error handling object")

class PromptFromFileToFileSchema(BaseModel):
    abs_file_path: str = Field(..., description="Absolute path to the file containing the prompt (must be an absolute path, not relative)")
    models_prefixed_by_provider: list[str] | str | None = Field(
        None,
        description="List of models with provider prefixes (e.g., 'openai:gpt-4o' or 'o:gpt-4o'). If not provided, uses default models."
    )
    abs_output_dir: str = Field(
        default=".",
        description="Absolute directory path to save the response files to (must be an absolute path, not relative. Default: current directory)"
    )
    error_strategy: dict[str, Any] | str | None = Field(None, description="Optional error handling object")

class ListProvidersSchema(BaseModel):
    pass

class ListModelsSchema(BaseModel):
    provider: str = Field(..., description="Provider to list models for (e.g., 'openai' or 'o')")


class ListGatewayModelsSchema(BaseModel):
    detailed: bool = Field(False, description="Return full gateway model records instead of only model IDs")


class CallModelProtocolSchema(BaseModel):
    model: str = Field(..., description="Model ID from the gateway model list")
    protocol: str = Field(
        default="auto",
        description="Protocol ID or 'auto'. Examples: openai:chat-completions, anthropic:messages, gemini:generate-content, openai:image-generations, seedance:generations, bocha:web-search.",
    )
    payload: dict[str, Any] | str | None = Field(
        None,
        description="Protocol request body. The model field is added automatically only for protocols that expect it.",
    )
    options: dict[str, Any] | str | None = Field(
        None,
        description="Optional gateway call options: api_key, base_url, timeout, strict_model_protocol.",
    )


class GetModelTaskSchema(BaseModel):
    protocol: str = Field(..., description="Async protocol ID such as seedance:generations or happyhorse:video-synthesis")
    task_id: str = Field(..., description="Task ID returned by the async submit call")
    options: dict[str, Any] | str | None = Field(None, description="Optional gateway call options: api_key, base_url, timeout")

class CEOAndBoardSchema(BaseModel):
    abs_file_path: str = Field(..., description="Absolute path to the file containing the prompt (must be an absolute path, not relative)")
    models_prefixed_by_provider: list[str] | str | None = Field(
        None,
        description="List of models with provider prefixes to act as board members. If not provided, uses default models."
    )
    abs_output_dir: str = Field(
        default=".",
        description="Absolute directory path to save the response files and CEO decision (must be an absolute path, not relative)"
    )
    ceo_model: str = Field(
        default=DEFAULT_CEO_MODEL,
        description="Model to use for the CEO decision in format 'provider:model'"
    )
    error_strategy: dict[str, Any] | str | None = Field(None, description="Optional error handling object")


async def serve(default_models: str = DEFAULT_MODEL) -> None:
    """
    Start the MCP server.
    
    Args:
        default_models: Comma-separated list of default models to use for prompts and corrections
    """
    # Set global default models for prompts and corrections
    os.environ["DEFAULT_MODELS"] = default_models

    # Parse default models into a list
    default_models_list = [model.strip() for model in default_models.split(",")]

    # Set the first model as the correction model
    correction_model = default_models_list[0] if default_models_list else "o:gpt-4o-mini"
    os.environ["CORRECTION_MODEL"] = correction_model

    logger.info(f"Starting server with default models: {default_models}")
    logger.info(f"Using correction model: {correction_model}")

    # Check and log provider availability
    print_provider_availability()

    # Create the MCP server
    server = Server("just-prompt")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Register all available tools with the MCP server."""
        return [
            Tool(
                name=JustPromptTools.ASK_MODEL,
                description="Ask exactly one model. Unprefixed model IDs are sent to the configured OpenAI-compatible gateway.",
                inputSchema=AskModelSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.MIMO_V2_5_TTS,
                description="Generate speech with the gateway model mimo-v2.5-tts. Uses assistant-role chat audio by default and saves returned audio bytes, base64, hex, or URL media to a local file.",
                inputSchema=GatewaySpeechSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.MINIMAX_SPEECH_2_8_TURBO,
                description="Generate speech with the gateway model minimax-speech-2.8-turbo. Uses assistant-role chat audio by default and saves returned audio bytes, base64, hex, or URL media to a local file when the gateway has a live endpoint.",
                inputSchema=GatewaySpeechSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.MINIMAX_M3_FREE,
                description="Ask the gateway chat model minimax-m3:free through non-streaming OpenAI chat completions.",
                inputSchema=GatewayChatSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.GPT_IMAGE_2,
                description="Generate an image with the gateway model gpt-image-2 through OpenAI image generations. Saves returned base64 image data or downloaded image URLs to a local file.",
                inputSchema=GptImage2Schema.schema(),
            ),
            Tool(
                name=JustPromptTools.GROK_4_20_MULTI_AGENT_XHIGH,
                description=(
                    "Highest-priority AI research/search synthesis via grok-4.20-multi-agent-xhigh. "
                    "Use this before lighter search tools when current external evidence quality matters and latency is acceptable.\n"
                    "\n"
                    "Non-streaming and slow. Prefer it for difficult research questions, source comparison, recent facts, "
                    "and high-stakes synthesis. The Chinese community on linux.do calls it \"传奇搜索大王\"; it is especially "
                    "strong for real-time X data plus academic paper, policy, official report, and market synthesis.\n"
                    "\n"
                    "Best practice: precisely define scope and depth; specify required research dimensions, data freshness, "
                    "and source quality. Force structured output such as Executive Summary, Findings with inline citations, "
                    "Agent Debate Highlights, Uncertainties/Gaps, Sources, and Recommendations. Prefer English prompts for stronger consistency.\n"
                    "\n"
                    "Default gateway timeout is 1200s; override via options.timeout. Treat timeouts or gateway errors as a signal "
                    "to retry or fall back to a lighter search tool."
                ),
                inputSchema=GrokSearchSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.PROMPT,
                description="Send a prompt to multiple LLM models",
                inputSchema=PromptSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.PROMPT_FROM_FILE,
                description="Send a prompt from a file to multiple LLM models. IMPORTANT: You MUST provide an absolute file path (e.g., /path/to/file or C:\\path\\to\\file), not a relative path.",
                inputSchema=PromptFromFileSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.PROMPT_FROM_FILE_TO_FILE,
                description="Send a prompt from a file to multiple LLM models and save responses to files. IMPORTANT: You MUST provide absolute paths (e.g., /path/to/file or C:\\path\\to\\file) for both file and output directory, not relative paths.",
                inputSchema=PromptFromFileToFileSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.CEO_AND_BOARD,
                description="Send a prompt to multiple 'board member' models and have a 'CEO' model make a decision based on their responses. IMPORTANT: You MUST provide absolute paths (e.g., /path/to/file or C:\\path\\to\\file) for both file and output directory, not relative paths.",
                inputSchema=CEOAndBoardSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.LIST_PROVIDERS,
                description="List all available LLM providers",
                inputSchema=ListProvidersSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.LIST_MODELS,
                description="List all available models for a specific LLM provider",
                inputSchema=ListModelsSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.LIST_GATEWAY_MODELS,
                description="List models exposed by the configured OpenAI-compatible gateway, including supported_protocols when detailed=true.",
                inputSchema=ListGatewayModelsSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.CALL_MODEL_PROTOCOL,
                description="Call a documented gateway protocol endpoint for chat, embeddings, images, video, speech, OCR, search, or web reader models.",
                inputSchema=CallModelProtocolSchema.schema(),
            ),
            Tool(
                name=JustPromptTools.GET_MODEL_TASK,
                description="Poll an async video generation task for protocols that return task IDs.",
                inputSchema=GetModelTaskSchema.schema(),
            ),
        ]

    # ----- blocking tool handlers (run via asyncio.to_thread) -----

    def _handle_ask_model(arguments: dict[str, Any]) -> str:
        options = parse_json_object_parameter(arguments.get("options"), "options")
        return ask_model(arguments["model"], arguments["prompt"], options)

    def _handle_speech(generator, arguments: dict[str, Any]) -> str:
        payload = parse_json_object_parameter(arguments.get("payload"), "payload")
        options = parse_json_object_parameter(arguments.get("options"), "options")
        return generator(
            text=arguments["text"],
            voice_id=arguments.get("voice_id"),
            output_path=arguments.get("output_path"),
            speed=_optional_float_argument(arguments.get("speed")),
            volume=_optional_float_argument(arguments.get("volume")),
            pitch=_optional_int_argument(arguments.get("pitch")),
            sample_rate=_optional_int_argument(arguments.get("sample_rate")),
            bitrate=_optional_int_argument(arguments.get("bitrate")),
            audio_format=arguments.get("audio_format"),
            channel=_optional_int_argument(arguments.get("channel")),
            language_boost=arguments.get("language_boost"),
            emotion=arguments.get("emotion"),
            subtitle_enable=_optional_bool_argument(arguments.get("subtitle_enable")),
            payload=payload,
            options=options,
        )

    def _handle_minimax_m3_free(arguments: dict[str, Any]) -> str:
        payload = parse_json_object_parameter(arguments.get("payload"), "payload")
        options = parse_json_object_parameter(arguments.get("options"), "options")
        return ask_minimax_m3_free(
            prompt=arguments["prompt"],
            system_prompt=arguments.get("system_prompt"),
            temperature=arguments.get("temperature"),
            max_tokens=arguments.get("max_tokens"),
            top_p=arguments.get("top_p"),
            payload=payload,
            options=options,
        )

    def _handle_gpt_image_2(arguments: dict[str, Any]) -> str:
        payload = parse_json_object_parameter(arguments.get("payload"), "payload")
        options = parse_json_object_parameter(arguments.get("options"), "options")
        return generate_gpt_image_2(
            prompt=arguments["prompt"],
            output_path=arguments.get("output_path"),
            size=arguments.get("size"),
            quality=arguments.get("quality"),
            n=_optional_int_argument(arguments.get("n")),
            background=arguments.get("background"),
            moderation=arguments.get("moderation"),
            output_format=arguments.get("output_format"),
            output_compression=_optional_int_argument(arguments.get("output_compression")),
            payload=payload,
            options=options,
        )

    def _handle_grok(arguments: dict[str, Any]) -> str:
        search_parameters = parse_json_object_parameter(
            arguments.get("search_parameters"),
            "search_parameters",
        )
        payload = parse_json_object_parameter(arguments.get("payload"), "payload")
        options = parse_json_object_parameter(arguments.get("options"), "options")
        return ask_grok_4_20_multi_agent_xhigh(
            query=arguments["query"],
            system_prompt=arguments.get("system_prompt"),
            temperature=arguments.get("temperature"),
            max_tokens=arguments.get("max_tokens"),
            top_p=arguments.get("top_p"),
            search_parameters=search_parameters,
            payload=payload,
            options=options,
        )

    def _format_multi_model(responses: list[str], models_to_use: list[str] | None) -> str:
        models_used = models_to_use if models_to_use else [
            model.strip() for model in os.environ.get("DEFAULT_MODELS", DEFAULT_MODEL).split(",")
        ]
        return "\n".join(
            f"Model: {models_used[i]}\nResponse: {resp}"
            for i, resp in enumerate(responses)
        )

    def _handle_prompt(arguments: dict[str, Any]) -> str:
        models_to_use = parse_json_array_parameter(
            arguments.get("models_prefixed_by_provider"),
            "models_prefixed_by_provider",
        )
        error_strategy = parse_json_object_parameter(arguments.get("error_strategy"), "error_strategy")
        responses = prompt(arguments["text"], models_to_use, error_strategy=error_strategy)
        return _format_multi_model(responses, models_to_use)

    def _handle_prompt_from_file(arguments: dict[str, Any]) -> str:
        models_to_use = parse_json_array_parameter(
            arguments.get("models_prefixed_by_provider"),
            "models_prefixed_by_provider",
        )
        error_strategy = parse_json_object_parameter(arguments.get("error_strategy"), "error_strategy")
        responses = prompt_from_file(
            arguments["abs_file_path"],
            models_to_use,
            error_strategy=error_strategy,
        )
        return _format_multi_model(responses, models_to_use)

    def _handle_prompt_from_file_to_file(arguments: dict[str, Any]) -> str:
        output_dir = arguments.get("abs_output_dir", ".")
        models_to_use = parse_json_array_parameter(
            arguments.get("models_prefixed_by_provider"),
            "models_prefixed_by_provider",
        )
        error_strategy = parse_json_object_parameter(arguments.get("error_strategy"), "error_strategy")
        file_paths = prompt_from_file_to_file(
            arguments["abs_file_path"],
            models_to_use,
            output_dir,
            error_strategy=error_strategy,
        )
        return "Responses saved to:\n" + "\n".join(file_paths)

    def _handle_list_providers(_: dict[str, Any]) -> str:
        providers = list_providers_func()
        provider_text = "\nAvailable Providers:\n"
        for provider in providers:
            alias_text = f", aliases='{provider['aliases']}'" if provider.get("aliases") else ""
            provider_text += (
                f"- {provider['name']}: full_name='{provider['full_name']}', "
                f"short_name='{provider['short_name']}'{alias_text}\n"
            )
        return provider_text

    def _handle_list_models(arguments: dict[str, Any]) -> str:
        models = list_models_func(arguments["provider"])
        return (
            f"Models for provider '{arguments['provider']}':\n"
            + "\n".join([f"- {model}" for model in models])
        )

    def _handle_list_gateway_models(arguments: dict[str, Any]) -> str:
        detailed = bool(arguments.get("detailed", False))
        records = list_gateway_model_details()
        model_ids = [
            str(
                record.get("id")
                or record.get("name")
                or record.get("model_id")
                or ""
            ).replace("models/", "", 1)
            for record in records
        ]
        if detailed:
            return json.dumps(records, ensure_ascii=False, indent=2)
        return "\n".join([model_id for model_id in model_ids if model_id])

    def _handle_call_model_protocol(arguments: dict[str, Any]) -> str:
        payload = parse_json_object_parameter(arguments.get("payload"), "payload")
        options = parse_json_object_parameter(arguments.get("options"), "options")
        response = call_model_protocol(
            arguments["model"],
            arguments.get("protocol", "auto"),
            payload=payload,
            options=options,
        )
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False, indent=2)

    def _handle_get_model_task(arguments: dict[str, Any]) -> str:
        options = parse_json_object_parameter(arguments.get("options"), "options")
        response = get_model_task(arguments["protocol"], arguments["task_id"], options=options)
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False, indent=2)

    def _handle_ceo_and_board(arguments: dict[str, Any]) -> str:
        file_path = arguments["abs_file_path"]
        output_dir = arguments.get("abs_output_dir", ".")
        models_to_use = parse_json_array_parameter(
            arguments.get("models_prefixed_by_provider"),
            "models_prefixed_by_provider",
        )
        ceo_model = arguments.get("ceo_model", DEFAULT_CEO_MODEL)
        error_strategy = parse_json_object_parameter(arguments.get("error_strategy"), "error_strategy")

        ceo_decision_file = ceo_and_board_prompt(
            abs_from_file=file_path,
            abs_output_dir=output_dir,
            models_prefixed_by_provider=models_to_use,
            ceo_model=ceo_model,
            error_strategy=error_strategy,
        )
        ceo_prompt_file = str(Path(ceo_decision_file).parent / "ceo_prompt.xml")
        return (
            f"Board responses and CEO decision saved.\n"
            f"CEO prompt file: {ceo_prompt_file}\n"
            f"CEO decision file: {ceo_decision_file}"
        )

    # Maps tool name -> blocking handler. Handlers are plain functions that do
    # network/file I/O; call_tool runs each via asyncio.to_thread so the stdio
    # server's event loop stays responsive during long (up to 1200s) model calls.
    def _blocking_handler_for(name: str) -> Callable[[dict[str, Any]], str] | None:
        if name == JustPromptTools.ASK_MODEL:
            return _handle_ask_model
        if name == JustPromptTools.MIMO_V2_5_TTS:
            return lambda a: _handle_speech(generate_mimo_v2_5_tts, a)
        if name == JustPromptTools.MINIMAX_SPEECH_2_8_TURBO:
            return lambda a: _handle_speech(generate_minimax_speech_2_8_turbo, a)
        if name == JustPromptTools.MINIMAX_M3_FREE:
            return _handle_minimax_m3_free
        if name == JustPromptTools.GPT_IMAGE_2:
            return _handle_gpt_image_2
        if name == JustPromptTools.GROK_4_20_MULTI_AGENT_XHIGH:
            return _handle_grok
        if name == JustPromptTools.PROMPT:
            return _handle_prompt
        if name == JustPromptTools.PROMPT_FROM_FILE:
            return _handle_prompt_from_file
        if name == JustPromptTools.PROMPT_FROM_FILE_TO_FILE:
            return _handle_prompt_from_file_to_file
        if name == JustPromptTools.LIST_PROVIDERS:
            return _handle_list_providers
        if name == JustPromptTools.LIST_MODELS:
            return _handle_list_models
        if name == JustPromptTools.LIST_GATEWAY_MODELS:
            return _handle_list_gateway_models
        if name == JustPromptTools.CALL_MODEL_PROTOCOL:
            return _handle_call_model_protocol
        if name == JustPromptTools.GET_MODEL_TASK:
            return _handle_get_model_task
        if name == JustPromptTools.CEO_AND_BOARD:
            return _handle_ceo_and_board
        return None

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls from the MCP client."""
        logger.info("Tool call: %s, arguments: %s", name, _redacted_tool_arguments(arguments))

        handler = _blocking_handler_for(name)
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        try:
            # Run the blocking molecule work in a worker thread so the event
            # loop can keep servicing stdio while a model call is in flight.
            text = await asyncio.to_thread(handler, arguments)
            return [TextContent(type="text", text=text)]
        except Exception as e:
            logger.error(f"Error handling tool call: {name}, error: {e}")
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]

    # Initialize and run the server
    try:
        options = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, options, raise_exceptions=True)
    except Exception as e:
        logger.error(f"Error running server: {e}")
        raise
