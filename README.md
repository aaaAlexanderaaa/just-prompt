# Just Prompt - A lightweight MCP server for LLM providers

`just-prompt` is a Model Context Protocol (MCP) server that exposes LLMs as tools. It can call a configured OpenAI-compatible or multi-protocol model gateway, and still supports direct provider calls for OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, and Ollama. See how we use the `ceo_and_board` tool to make [hard decisions easy with o3 here](https://youtu.be/LEMLntjfihA).

<img src="images/just-prompt-logo.png" alt="Just Prompt Logo" width="700" height="auto">

<img src="images/o3-as-a-ceo.png" alt="Just Prompt Logo" width="700" height="auto">


## Tools

The following MCP tools are available in the server:

- **`ask_model`**: Ask exactly one model through the configured gateway or a known provider prefix
  - Parameters:
    - `model`: Model ID. Unprefixed IDs are sent to the configured OpenAI-compatible gateway and use model metadata to auto-select a compatible protocol.
    - `prompt`: The prompt text
    - `options` (optional): Gateway options such as `protocol` (`auto` by default), `temperature`, `max_tokens`, `top_p`, `base_url`, `api_key`, `timeout`, and `payload` overrides

- **`mimo_v2_5_tts`**: Generate speech with `mimo-v2.5-tts`
  - Parameters:
    - `text` (required): Text to synthesize
    - `voice_id` (default: `male-qn-qingse`, used by speech protocols that accept one)
    - `output_path` (optional): Audio output path. Defaults to `generated/mimo-v2.5-tts-<utc>.mp3`
    - `payload` / `options` (optional): Raw payload overrides and gateway options. Uses assistant-role chat audio by default; pass `options.protocol` as `openai:audio-speech` or `minimax:t2a_v2` when your gateway supports those routes.
  - Output: JSON with `saved_audio_path` and `saved_audio_bytes`; URL audio responses are downloaded before the tool returns.

- **`minimax_speech_2_8_turbo`**: Generate speech with `minimax-speech-2.8-turbo`
  - Parameters are the same as `mimo_v2_5_tts`
  - Limitation: the integration test gateway returned `no_endpoints_available` for this model on 2026-06-06, so the tool is registered but may not be callable until the gateway exposes a live endpoint.

- **`minimax_m3_free`**: Ask `minimax-m3:free` through non-streaming OpenAI chat completions
  - Parameters:
    - `prompt` (required)
    - `system_prompt`, `temperature`, `max_tokens`, `top_p` (optional)
    - `payload` / `options` (optional)
  - Output: plain text from the model.

- **`gpt_image_2`**: Generate images with `gpt-image-2`
  - Parameters:
    - `prompt` (required)
    - `output_path` (optional): Image output path. Defaults to `generated/gpt-image-2-<utc>.png`
    - `size` (default: `auto`), `quality` (default: `auto`), `n` (default: `1`), `background`, `moderation`, `output_format` (default: `png`), `output_compression`
    - `payload` / `options` (optional)
  - Output: JSON with `saved_image_paths` and `saved_image_bytes`; URL image responses are downloaded before the tool returns.

- **`grok_4_20_multi_agent_xhigh`**: Ask the long-running, non-streaming search model `grok-4.20-multi-agent-xhigh`
  - Parameters:
    - `query` (required)
    - `system_prompt`, `temperature`, `max_tokens`, `top_p`, `search_parameters` (optional)
    - `payload` / `options` (optional)
  - Output: plain text from the model. Default timeout is longer than normal chat calls.

- **`prompt`**: Send a prompt to multiple LLM models
  - Parameters:
    - `text`: The prompt text
    - `models_prefixed_by_provider` (optional): List of models with provider prefixes. If not provided, uses default models.
    - `error_strategy` (optional): `{ "strategy": "best_effort" | "all_or_nothing" | "retry_with_backoff", "max_retries": 3, "backoff_seconds": 1 }`

- **`prompt_from_file`**: Send a prompt from a file to multiple LLM models
  - Parameters:
    - `abs_file_path`: Absolute path to the file containing the prompt (must be an absolute path, not relative)
    - `models_prefixed_by_provider` (optional): List of models with provider prefixes. If not provided, uses default models.

- **`prompt_from_file_to_file`**: Send a prompt from a file to multiple LLM models and save responses as markdown files
  - Parameters:
    - `abs_file_path`: Absolute path to the file containing the prompt (must be an absolute path, not relative)
    - `models_prefixed_by_provider` (optional): List of models with provider prefixes. If not provided, uses default models.
    - `abs_output_dir` (default: "."): Absolute directory path to save the response markdown files to (must be an absolute path, not relative)

- **`ceo_and_board`**: Send a prompt to multiple 'board member' models and have a 'CEO' model make a decision based on their responses
  - Parameters:
    - `abs_file_path`: Absolute path to the file containing the prompt (must be an absolute path, not relative)
    - `models_prefixed_by_provider` (optional): List of models with provider prefixes to act as board members. If not provided, uses default models.
    - `abs_output_dir` (default: "."): Absolute directory path to save the response files and CEO decision (must be an absolute path, not relative)
    - `ceo_model` (default: "openai:o3"): Model to use for the CEO decision in format "provider:model"

- **`list_providers`**: List all available LLM providers
  - Parameters: None

- **`list_models`**: List all available models for a specific LLM provider
  - Parameters:
    - `provider`: Provider to list models for (e.g., 'openai' or 'o')

- **`list_gateway_models`**: List models from the configured gateway
  - Parameters:
    - `detailed` (optional): Return full records, including `supported_protocols`, instead of just IDs

- **`call_model_protocol`**: Call a documented gateway protocol endpoint for models that are not plain chat models
  - Parameters:
    - `model`: Model ID
    - `protocol`: `auto` or a protocol ID such as `openai:chat-completions`, `anthropic:messages`, `gemini:generate-content`, `openai:image-generations`, `openai:audio-speech`, `openai:embeddings`, `seedance:generations`, `minimax:t2a_v2`, `zai:layout-parsing`, `bocha:web-search`, `unifuncs:web-search`, or `unifuncs:web-reader`
    - `payload`: Protocol request body. The `model` field is added automatically when the protocol expects it in JSON.
    - `options` (optional): `api_key`, `base_url`, `timeout`, `strict_model_protocol`

- **`get_model_task`**: Poll async video-generation tasks for protocols with documented task endpoints
  - Parameters:
    - `protocol`: Async protocol ID such as `seedance:generations` or `happyhorse:video-synthesis`
    - `task_id`: Task ID returned by the submit call

## Provider Prefixes
> the legacy multi-model tools use provider prefixes
>
> use the short name for faster referencing

- `o` or `openai`: OpenAI 
  - `o:gpt-4o-mini`
  - `openai:gpt-4o-mini`
- `a` or `anthropic`: Anthropic 
  - `a:claude-3-5-haiku`
  - `anthropic:claude-3-5-haiku`
- `g` or `gemini`: Google Gemini 
  - `g:gemini-2.5-pro-exp-03-25`
  - `gemini:gemini-2.5-pro-exp-03-25`
- `q` or `groq`: Groq 
  - `q:llama-3.1-70b-versatile`
  - `groq:llama-3.1-70b-versatile`
- `d` or `deepseek`: DeepSeek 
  - `d:deepseek-coder`
  - `deepseek:deepseek-coder`
- `l` or `ollama`: Ollama 
  - `l:llama3.1`
  - `ollama:llama3.1`
- `gw` or `gateway`: Generic OpenAI-compatible or multi-protocol gateway
  - `gw:glm-4.7`
  - `gateway:qwen3-max`
  - aliases: `oc`, `openai-compatible`, `llm`

## Generic Model Gateway

The gateway provider is the shortest path for a Model-as-Tool setup:

```text
main agent -> MCP client -> ask_model(model, prompt, options?) -> your gateway -> model
```

Configure the gateway explicitly:

```bash
MODEL_GATEWAY_BASE_URL=https://your-gateway.example.com/v1
MODEL_GATEWAY_PROTOCOL_BASE_URL=https://your-gateway.example.com
MODEL_GATEWAY_API_KEY=your_gateway_api_key
```

For a plain OpenAI-compatible API gateway, `MODEL_GATEWAY_PROTOCOL_BASE_URL` can be omitted:

```bash
MODEL_GATEWAY_BASE_URL=https://your-gateway.example.com/v1
MODEL_GATEWAY_API_KEY=your_gateway_api_key
```

Use `ask_model` for the common "one prompt in, one result out" path. It looks at gateway model metadata and automatically selects the first compatible protocol it knows how to call:

```json
{
  "model": "glm-4.7",
  "prompt": "Summarize the tradeoffs of MCP model-as-tool wrappers.",
  "options": { "temperature": 0.2 }
}
```

Use `call_model_protocol` for non-chat gateway models. Examples:

```json
{
  "model": "qwen-text-embedding-v4",
  "protocol": "openai:embeddings",
  "payload": { "input": "semantic search query" }
}
```

For the fixed models added above, prefer the dedicated MCP tools. They set the
right model IDs, force non-streaming calls where needed, use longer timeouts for
slow image/search requests, and save base64, hex, binary, or URL media responses
to local files.

## Dedicated Gateway Model Tools

These tools use `MODEL_GATEWAY_BASE_URL` and `MODEL_GATEWAY_API_KEY`. Set them
in `.env`, export them in your shell, or pass them through your MCP client's
environment configuration.

Media outputs are written inside the configured file root. By default that is
the MCP server's current working directory; set `JUST_PROMPT_FILE_ROOT` if you
want generated files under a different allowed directory. If `output_path` is
omitted, files are saved under `generated/`.

### `mimo_v2_5_tts`

Generates speech with `mimo-v2.5-tts`.

Required:

- `text`: text to synthesize.

Defaults:

- `output_path`: `generated/mimo-v2.5-tts-<utc>.mp3`
- `audio_format`: `mp3`
- `options.protocol`: `auto`, resolved by this tool to `openai:chat-completions`
- gateway timeout: `300` seconds
- media URL download timeout: `120` seconds

Accepted parameters:

- `voice_id`, `speed`, `volume`, `pitch`, `sample_rate`, `bitrate`, `audio_format`, `channel`, `language_boost`, `emotion`, `subtitle_enable`
- `payload`: raw request body overrides
- `options`: `protocol`, `api_key`, `base_url`, `timeout`, `media_download_timeout`

Protocol notes:

- The current working route for `mimo-v2.5-tts` is assistant-role OpenAI chat audio.
- `voice_id` and detailed voice/audio settings are only meaningful when the gateway supports `openai:audio-speech` or `minimax:t2a_v2`; the default chat-audio route may ignore them.
- The tool finishes only after it saves an audio file. It handles raw bytes, hex, base64, data URLs, and HTTP(S) media URLs.

Minimal call:

```json
{
  "text": "请用自然旁白语气朗读这段家庭档案说明。"
}
```

Typical result:

```json
{
  "saved_audio_path": "/path/to/just-prompt/generated/mimo-v2.5-tts-20260606T011609Z.mp3",
  "saved_audio_bytes": 299564
}
```

### `minimax_speech_2_8_turbo`

Registered as a speech tool for `minimax-speech-2.8-turbo` with the same
parameters and output contract as `mimo_v2_5_tts`.

Known limitation:

- On 2026-06-06, the configured OneAPI gateway returned `no_endpoints_available` for this model through the checked routes. That means the MCP tool is present, but the gateway currently has no usable backend endpoint for it.

### `minimax_m3_free`

Calls `minimax-m3:free` through non-streaming OpenAI chat completions.

Required:

- `prompt`: user prompt.

Optional parameters:

- `system_prompt`: system instruction.
- `temperature`, `top_p`: sampling controls.
- `max_tokens`: hard output-length cap. Use it only when you specifically want truncation; omit it for normal full-answer behavior.
- `payload`: raw chat-completions overrides.
- `options`: `api_key`, `base_url`, `timeout`.

Minimal call:

```json
{
  "prompt": "给我三条家庭知识库整理建议。"
}
```

### `gpt_image_2`

Generates an image with `gpt-image-2` through OpenAI image generations.

Required:

- `prompt`: image prompt.

Defaults:

- `size`: `auto`
- `quality`: `auto`
- `n`: `1`
- `output_format`: `png`
- `output_path`: `generated/gpt-image-2-<utc>.png`
- gateway timeout: `900` seconds
- media URL download timeout: `120` seconds

Accepted parameters:

- `size`: `auto`, `1024x1024`, `1024x1536`, `1536x1024`, or another value accepted by the gateway/model.
- `quality`: `auto` or another explicit quality value accepted by the gateway/model. Leave it at `auto` for normal use.
- `n`: number of images. Default is `1`.
- `background`, `moderation`, `output_format`, `output_compression`
- `payload`: raw image-generation overrides.
- `options`: `api_key`, `base_url`, `timeout`, `media_download_timeout`.

Output contract:

- The tool finishes only after it saves local image files.
- It handles base64/data responses and HTTP(S) image URLs.
- Returned JSON includes `saved_image_paths` and `saved_image_bytes`; when the gateway returned a URL, it is retained as `source_image_urls` for traceability.

Prompt-only auto call:

```json
{
  "prompt": "A clean editorial illustration of a compact home lab desk, warm morning light, no text."
}
```

Explicit-size call:

```json
{
  "prompt": "A crisp square illustration of a compact home lab desk, warm morning light, no text.",
  "n": 1,
  "size": "1024x1024",
  "quality": "auto"
}
```

On this gateway, examples keep `quality` at `auto`; override it only when the
task itself requires a specific quality setting.

Typical result:

```json
{
  "saved_image_paths": ["/path/to/just-prompt/generated/gpt-image-2-20260606T012000Z.png"],
  "saved_image_bytes": [1048576],
  "source_image_urls": ["https://example-cdn.invalid/generated-image.png"]
}
```

### `grok_4_20_multi_agent_xhigh`

Calls the long-running, non-streaming search model
`grok-4.20-multi-agent-xhigh` through OpenAI chat completions.

Required:

- `query`: research/search question.

Optional parameters:

- `system_prompt`: system instruction.
- `temperature`, `top_p`: sampling controls.
- `max_tokens`: hard output-length cap. Use it only when you specifically want truncation; omit it for normal full-answer behavior.
- `search_parameters`: provider-specific search options.
- `payload`: raw chat-completions overrides.
- `options`: `api_key`, `base_url`, `timeout`.

Defaults:

- `stream`: `false`
- gateway timeout: `1200` seconds

Example:

```json
{
  "query": "Find recent privacy-minded local AI tooling for home lab operators. Give three concise bullets with dates."
}
```

```json
{
  "model": "unifuncs-web-search",
  "protocol": "unifuncs:web-search",
  "payload": { "query": "Model Context Protocol", "count": 5 }
}
```

```json
{
  "model": "bocha-web-search",
  "protocol": "bocha:web-search",
  "payload": { "query": "Alibaba 2024 ESG report", "count": 10 }
}
```

`list_gateway_models` with `detailed=true` returns each model's `supported_protocols`. The server uses this metadata for `auto` protocol selection, and clients can inspect it when they want to override the default.

When you already know the protocol, pass it explicitly:

```json
{
  "model": "gemini-2.5-pro",
  "protocol": "gemini:generate-content",
  "payload": { "prompt": "Explain MCP in one paragraph." }
}
```

## Features

- Unified API for multiple LLM providers
- Support for text prompts from strings or files
- Run multiple models in parallel
- Automatic model name correction using the first model in the `--default-models` list
- Ability to save responses to files
- Easy listing of available providers and models

## Installation

```bash
# Clone the repository
git clone https://github.com/disler/just-prompt.git
cd just-prompt

# Install with pip
uv sync
```

### Environment Variables

Create a `.env` file with your API keys (you can copy the `.env.sample` file):

```bash
cp .env.sample .env
```

Then edit the `.env` file to add your API keys (or export them in your shell):

```
OPENAI_API_KEY=your_openai_api_key_here
MODEL_GATEWAY_API_KEY=your_gateway_api_key_here
MODEL_GATEWAY_BASE_URL=https://your-gateway.example.com/v1
MODEL_GATEWAY_PROTOCOL_BASE_URL=https://your-gateway.example.com
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OLLAMA_HOST=http://localhost:11434
```

File-based tools are restricted to the server's current working directory by default. Set `JUST_PROMPT_FILE_ROOT` or pass `--file-access-root` to allow reads and writes inside a different directory.

## Claude Code Installation
> In all these examples, replace the directory with the path to the just-prompt directory.

Default models are set to the gateway provider (`gateway:glm-4.7`) unless you pass `--default-models`.

If you use Claude Code right out of the repository you can see in the .mcp.json file we set the default models to...

```
{
  "mcpServers": {
    "just-prompt": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        ".",
        "run",
        "just-prompt",
        "--default-models",
        "gateway:glm-4.7"
      ],
      "env": {}
    }
  }
}
```

The `--default-models` parameter sets the models to use when none are explicitly provided to the API endpoints. The first model in the list is also used for model name correction when needed. This can be a list of models separated by commas.

When starting the server, it will automatically check which API keys are available in your environment and inform you which providers you can use. If a key is missing, the provider will be listed as unavailable, but the server will still start and can be used with the providers that are available.

### Using `mcp add-json`

For Claude Code's JSON form use:

```
claude mcp add-json just-prompt "$(pbpaste)"
```

JSON to copy

```
{
    "command": "uv",
    "args": ["--directory", ".", "run", "just-prompt"]
}
```

With a custom default gateway model:

```
{
    "command": "uv",
    "args": ["--directory", ".", "run", "just-prompt", "--default-models", "gateway:qwen3-max"]
}
```

With multiple default models:

```
{
    "command": "uv",
    "args": ["--directory", ".", "run", "just-prompt", "--default-models", "gateway:glm-4.7,gateway:qwen3-max,gateway:deepseek-v3.2"]
}
```

### Using `mcp add` with project scope

```bash
# With default models
claude mcp add just-prompt -s project \
  -- \
    uv --directory . \
    run just-prompt

# With custom default model
claude mcp add just-prompt -s project \
  -- \
  uv --directory . \
  run just-prompt --default-models "gateway:qwen3-max"

# With multiple default models
claude mcp add just-prompt -s user \
  -- \
  uv --directory . \
  run just-prompt --default-models "gateway:glm-4.7,gateway:qwen3-max,gateway:deepseek-v3.2"
```


## `mcp remove`

claude mcp remove just-prompt

## Running Tests

```bash
uv run pytest
```

## Codebase Structure

```
.
├── ai_docs/                   # Documentation for AI model details
│   ├── extending_thinking_sonny.md
│   ├── llm_providers_details.xml
│   ├── openai-reasoning-effort.md
│   └── pocket-pick-mcp-server-example.xml
├── example_outputs/           # Example outputs from different models
├── list_models.py             # Script to list available LLM models
├── prompts/                   # Example prompt files
├── pyproject.toml             # Python project configuration
├── specs/                     # Project specifications
│   ├── init-just-prompt.md
│   ├── new-tool-llm-as-a-ceo.md
│   └── oai-reasoning-levels.md
├── src/                       # Source code directory
│   └── just_prompt/
│       ├── __init__.py
│       ├── __main__.py
│       ├── atoms/             # Core components
│       │   ├── llm_providers/ # Individual provider implementations
│       │   │   ├── anthropic.py
│       │   │   ├── deepseek.py
│       │   │   ├── gateway.py
│       │   │   ├── gemini.py
│       │   │   ├── groq.py
│       │   │   ├── ollama.py
│       │   │   └── openai.py
│       │   └── shared/        # Shared utilities and data types
│       │       ├── data_types.py
│       │       ├── file_access.py
│       │       ├── model_router.py
│       │       ├── parameters.py
│       │       ├── utils.py
│       │       └── validator.py
│       ├── molecules/         # Higher-level functionality
│       │   ├── ask_model.py
│       │   ├── ceo_and_board_prompt.py
│       │   ├── list_models.py
│       │   ├── list_providers.py
│       │   ├── prompt.py
│       │   ├── prompt_from_file.py
│       │   └── prompt_from_file_to_file.py
│       ├── server.py          # MCP server implementation
│       └── tests/             # Test directory
│           ├── atoms/         # Tests for atoms
│           │   ├── llm_providers/
│           │   └── shared/
│           └── molecules/     # Tests for molecules
│               ├── test_ceo_and_board_prompt.py
│               ├── test_list_models.py
│               ├── test_list_providers.py
│               ├── test_prompt.py
│               ├── test_prompt_from_file.py
│               └── test_prompt_from_file_to_file.py
└── ultra_diff_review/         # Diff review outputs
```

## Context Priming
READ README.md, pyproject.toml, then run git ls-files, and 'eza --git-ignore --tree' to understand the context of the project.

# Reasoning Effort with OpenAI o‑Series

For OpenAI o‑series reasoning models (`o4-mini`, `o3-mini`, `o3`) you can
control how much *internal* reasoning the model performs before producing a
visible answer.

Append one of the following suffixes to the model name (after the *provider*
prefix):

* `:low`   – minimal internal reasoning (faster, cheaper)
* `:medium` – balanced (default if omitted)
* `:high`  – thorough reasoning (slower, more tokens)

Examples:

* `openai:o4-mini:low`
* `o:o4-mini:high`

When a reasoning suffix is present, **just‑prompt** automatically switches to
the OpenAI *Responses* API (when available) and sets the corresponding
`reasoning.effort` parameter.  If the installed OpenAI SDK is older, it
gracefully falls back to the Chat Completions endpoint and embeds an internal
system instruction to approximate the requested effort level.

# Thinking Tokens with Claude

The Anthropic Claude models `claude-opus-4-20250514` and `claude-sonnet-4-20250514` support extended thinking capabilities using thinking tokens. This allows Claude to do more thorough thought processes before answering.

You can enable thinking tokens by adding a suffix to the model name in this format:
- `anthropic:claude-opus-4-20250514:1k` - Use 1024 thinking tokens for Opus 4
- `anthropic:claude-sonnet-4-20250514:4k` - Use 4096 thinking tokens for Sonnet 4
- `anthropic:claude-opus-4-20250514:8000` - Use 8000 thinking tokens for Opus 4

Notes:
- Thinking tokens are supported for `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, and `claude-3-7-sonnet-20250219` models
- Valid thinking token budgets range from 1024 to 16000
- Values outside this range will be automatically adjusted to be within range
- You can specify the budget with k notation (1k, 4k, etc.) or with exact numbers (1024, 4096, etc.)

# Thinking Budget with Gemini

The Google Gemini model `gemini-2.5-flash-preview-04-17` supports extended thinking capabilities using thinking budget. This allows Gemini to perform more thorough reasoning before providing a response.

You can enable thinking budget by adding a suffix to the model name in this format:
- `gemini:gemini-2.5-flash-preview-04-17:1k` - Use 1024 thinking budget
- `gemini:gemini-2.5-flash-preview-04-17:4k` - Use 4096 thinking budget
- `gemini:gemini-2.5-flash-preview-04-17:8000` - Use 8000 thinking budget

Notes:
- Thinking budget is only supported for the `gemini-2.5-flash-preview-04-17` model
- Valid thinking budget range from 0 to 24576
- Values outside this range will be automatically adjusted to be within range
- You can specify the budget with k notation (1k, 4k, etc.) or with exact numbers (1024, 4096, etc.)

## Resources
- https://docs.anthropic.com/en/api/models-list?q=list+models
- https://github.com/googleapis/python-genai
- https://platform.openai.com/docs/api-reference/models/list
- https://api-docs.deepseek.com/api/list-models
- https://github.com/ollama/ollama-python
- https://github.com/openai/openai-python

## Master AI Coding 
Learn to code with AI with foundational [Principles of AI Coding](https://agenticengineer.com/principled-ai-coding?y=jprompt)

Follow the [IndyDevDan youtube channel](https://www.youtube.com/@indydevdan) for more AI coding tips and tricks.
