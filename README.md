# Just Prompt - A lightweight MCP server for LLM providers

`just-prompt` is a Model Context Protocol (MCP) server that exposes LLMs as tools. It can call a configured OpenAI-compatible or multi-protocol model gateway, and still supports direct provider calls for OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, and Ollama. See how we use the `ceo_and_board` tool to make [hard decisions easy with o3 here](https://youtu.be/LEMLntjfihA).

<img src="images/just-prompt-logo.png" alt="Just Prompt Logo" width="700" height="auto">

<img src="images/o3-as-a-ceo.png" alt="Just Prompt Logo" width="700" height="auto">


## Tools

`just-prompt` exposes two kinds of MCP tools:

- Core tools that are always present.
- Gateway model tools declared by you in `just-prompt.config.json`.

The model-specific tools are not meant to be hard-coded in Python or in this
README. Add, remove, rename, or hide them by editing `gateway_model_tools`, then
restart the MCP server so the client can refresh its tool list.

Core tools:

- `ask_model`: ask exactly one model. Unprefixed model IDs go to the configured
  gateway; provider-prefixed IDs keep the legacy direct-provider routing.
- `prompt`, `prompt_from_file`, `prompt_from_file_to_file`, `ceo_and_board`:
  legacy multi-model workflows that use provider-prefixed model names.
- `list_providers`, `list_models`, `list_gateway_models`: inspect providers and
  gateway model metadata.
- `call_model_protocol`: call a specific gateway protocol endpoint for chat,
  image, speech, embedding, video, OCR, search, or reader models.
- `get_model_task`: poll async protocol tasks such as video generation jobs.

For one-off gateway calls, use `ask_model`:

```json
{
  "model": "kimi-k2.7-code",
  "prompt": "Review this code. Here is the full relevant file content: ...",
  "options": {
    "protocol": "auto",
    "timeout": 1200
  }
}
```

Important agent rules:

- The called cloud model only sees the prompt or payload you send. It cannot
  inspect local files, repositories, terminal output, screenshots, or previous
  tool results unless you include that content explicitly.
- Do not pass `max_tokens` by habit. It is a hard output cap. Omit it for normal
  full-answer behavior, or pass `0` where supported to have just-prompt treat it
  as uncapped.
- `options.timeout` is just-prompt's HTTP wait timeout. Slow gateway calls can
  take several minutes; use values such as `900`, `1200`, or `1800` seconds when
  the model is expected to be slow. Some MCP clients also enforce their own
  tool-call timeout outside just-prompt.

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
  - `gw:your-model-id`
  - `gateway:your-model-id`
  - aliases: `oc`, `openai-compatible`, `llm`

## Gateway Configuration

The gateway provider is the shortest path for a model-as-tool setup:

```text
main agent -> MCP client -> configured tool or ask_model -> your gateway -> model
```

Put non-secret runtime settings in `just-prompt.config.json`:

```json
{
  "gateway": {
    "base_url": "https://your-gateway.example.com/v1",
    "protocol_base_url": "https://your-gateway.example.com"
  },
  "file_access_root": "/absolute/path/allowed-for-file-tools"
}
```

Keep secrets in `.env` or your shell:

```bash
MODEL_GATEWAY_API_KEY=your_gateway_api_key
```

Config file roles are intentionally narrow:

- `just-prompt.config.json`: shared non-secret runtime config for CLI and MCP.
- `.env`: secrets and provider credentials.
- `.mcp.json`: MCP client launch command only.
- `pyproject.toml` and `uv.lock`: package/dependency metadata, not runtime config.

`just-prompt.config.json` is loaded first. `JUST_PROMPT_CONFIG_FILE` can point
to another JSON file to merge on top, and `JUST_PROMPT_CONFIG` can provide a
final inline JSON override.

## Configure Model Tools

Add gateway model tools under `gateway_model_tools`. You can use either an
object keyed by tool name or a list of objects with a `name` field.

```json
{
  "gateway_model_tools": {
    "research_web": {
      "model": "your-search-model-id",
      "category": "search",
      "description": "Use this for internet research only. Ask for sources, dates, and uncertainty; verify claims before treating them as facts.",
      "enabled": true
    },
    "image_creator": {
      "model": "your-image-model-id",
      "category": "image",
      "description": "Generate images through the configured gateway and save the returned media locally."
    },
    "tts_reader": {
      "model": "your-speech-model-id",
      "category": "speech",
      "description": "Generate speech through the configured gateway and save the returned audio locally."
    }
  }
}
```

Each entry needs:

- `name` when using list form, or the object key when using object form.
- `model`: the gateway model ID to send.
- `category`: one of `text`, `search`, `image`, or `speech`.
- `description`: the instruction shown to the agent in the MCP tool list.
- `enabled`: optional; set `false` to hide a tool without deleting the config.

Tool names cannot override core tools such as `ask_model`, `prompt`, or
`list_gateway_models`.

Choose the category by the shape of the call you want:

- `text`: input is `prompt`; optional `system_prompt`, `temperature`,
  `top_p`, `max_tokens`, `payload`, and `options`.
- `search`: input is `query`; optional `system_prompt`, `temperature`,
  `top_p`, `max_tokens`, `search_parameters`, `payload`, and `options`.
- `image`: input is `prompt`; optional `output_path`, `size`, `quality`, `n`,
  `background`, `moderation`, `output_format`, `output_compression`,
  `payload`, and `options`.
- `speech`: input is `text`; optional `voice_id`, `output_path`, `speed`,
  `volume`, `pitch`, `sample_rate`, `bitrate`, `audio_format`, `channel`,
  `language_boost`, `emotion`, `subtitle_enable`, `payload`, and `options`.

`payload` is merged into the final request body for adapter-specific fields.
`options` controls gateway plumbing such as `api_key`, `base_url`, `timeout`,
`protocol`, `strict_model_protocol`, and `media_download_timeout` where the
adapter supports them.

Search/research tool descriptions should be explicit about limits. A gateway
research model may have broader internet/source access and richer search loops,
but its final summary is still AI-generated and can be wrong. It searches the
internet, not your local files. If local code, logs, or private context matter,
put that content in the prompt or payload.

## Configure Defaults

`default_models` chooses which models the legacy multi-model tools use when a
call does not pass `models_prefixed_by_provider`. The first model is also used
for model-name correction.

`model_defaults` controls how configured gateway model tools and CLI adapters
call those models. Category defaults apply first; model-specific defaults
override them; explicit MCP or CLI arguments override both. Raw `payload` values
are merged last into the request body.

```json
{
  "default_models": "gateway:your-primary-model-id,gateway:your-review-model-id",
  "model_defaults": {
    "categories": {
      "text": {
        "timeout": 900,
        "max_tokens": 0
      },
      "search": {
        "timeout": 1200,
        "max_tokens": 0,
        "system_prompt": "Prefer primary sources, include concrete dates, and separate verified facts from inference."
      },
      "image": {
        "timeout": 900,
        "size": "4k",
        "quality": "auto",
        "n": 1,
        "output_format": "png"
      },
      "speech": {
        "timeout": 300,
        "audio_format": "mp3",
        "voice_id": "default-voice-id"
      }
    },
    "models": {
      "your-search-model-id": {
        "timeout": 1800,
        "query_template": "Research {topic}. Return sources, dates, confidence, and open questions."
      },
      "your-image-model-id": {
        "size": "2048x2048"
      }
    }
  }
}
```

Recommended default posture:

- Set generous timeouts for slow search, reasoning, media, and multi-step
  models. A client-side timeout does not prove the backend failed; it only means
  just-prompt stopped waiting.
- Leave `max_tokens` omitted or `0` unless you intentionally want truncation.
- Put model-specific prompting, evidence requirements, search parameters, image
  size, speech voice, and output formats in config so agents do not have to
  rediscover them on every call.

For CLI adapter selection, add `model_categories` when a model is not declared
as a `gateway_model_tools` entry:

```json
{
  "model_categories": {
    "your-image-model-id": "image",
    "your-search-model-id": "search"
  }
}
```

Media outputs are written inside the configured file root. By default that is
the MCP server's current working directory. Set `file_access_root`,
`JUST_PROMPT_FILE_ROOT`, or `--file-access-root` when generated media or
file-based prompts need another allowed directory. If `output_path` is omitted,
media tools save files under `generated/`; if it points to a directory, the tool
creates a timestamped filename inside that directory.

Use `call_model_protocol` when the gateway model is not a normal text, search,
image, or speech adapter call:

```json
{
  "model": "your-embedding-model-id",
  "protocol": "openai:embeddings",
  "payload": {
    "input": "semantic search query"
  },
  "options": {
    "timeout": 300
  }
}
```

`list_gateway_models` with `detailed=true` returns each model's advertised
`supported_protocols`. `protocol: "auto"` uses that metadata when possible; if
the gateway metadata is incomplete, pass the protocol explicitly or set
`strict_model_protocol` to `false` in `options`.

## One-Shot CLI Calls

`just-prompt` still starts the MCP stdio server by default. For direct shell
usage, use the `call` subcommand:

```bash
uv run just-prompt call MODEL [--category text|speech|image|search] [adapter options] [input]
```

The CLI chooses an adapter in this order:

- If `--category` is provided, use that adapter.
- If the model is declared in `gateway_model_tools`, use that tool's category.
- If the model is listed in `model_categories`, use that configured category.
- Otherwise, default to the `text` adapter.

To inspect the accepted parameters and defaults for the resolved adapter, ask
for help after the model name:

```bash
uv run just-prompt call your-image-model-id --category image --help
uv run just-prompt call your-search-model-id --help
uv run just-prompt call your-chat-model-id --help
```

Examples:

```bash
uv run just-prompt call your-chat-model-id "Give me three concise project naming ideas."
```

```bash
uv run just-prompt call your-image-model-id --category image "A crisp square illustration of a compact home lab desk, warm morning light, no text."
```

```bash
uv run just-prompt call your-speech-model-id --category speech --text "Read this in a calm narration voice."
```

```bash
uv run just-prompt call your-search-model-id --category search --query "Find recent privacy-minded local AI tooling for home lab operators. Give three concise bullets with dates."
```

Text adapter parameters:

- Primary input: positional input, `--prompt`, `--prompt-file`, or stdin.
- Optional: `--system-prompt`, `--system-prompt-file`, `--temperature`, `--top-p`, `--max-tokens`.
- Gateway plumbing: `--base-url`, `--api-key`, `--timeout`, `--payload`, `--options`.
- `--max-tokens` is a hard output-length cap; omit it for normal full-answer behavior.

Speech adapter parameters:

- Primary input: positional input, `--text`, `--text-file`, or stdin.
- Output: `--output-path` accepts a file path or directory; omitted paths default to `generated/<model>-<utc>.mp3`.
- Voice/audio: `--voice-id`, `--speed`, `--volume`, `--pitch`, `--sample-rate`, `--bitrate`, `--audio-format`, `--channel`, `--language-boost`, `--emotion`, `--subtitle-enable`.
- Protocol/gateway: `--protocol`, `--base-url`, `--api-key`, `--timeout`, `--media-download-timeout`, `--payload`, `--options`.

Image adapter parameters:

- Primary input: positional input, `--prompt`, `--prompt-file`, or stdin.
- Output: `--output-path` accepts a file path or directory; omitted paths default to `generated/<model>-<utc>.png`.
- Generation: `--size`, `--quality`, `--n`, `--background`, `--moderation`, `--output-format`, `--output-compression`.
- Gateway: `--base-url`, `--api-key`, `--timeout`, `--media-download-timeout`, `--payload`, `--options`.
- The command returns only after image data or image URLs have been saved as local files.

Search adapter parameters:

- Primary input: positional input, `--query`, `--query-file`, or stdin.
- Optional: `--system-prompt`, `--system-prompt-file`, `--temperature`, `--top-p`, `--max-tokens`, `--search-parameters`.
- Gateway: `--base-url`, `--api-key`, `--timeout`, `--payload`, `--options`.
- `--max-tokens` is a hard output-length cap; omit it for normal full-answer behavior.

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

Then edit the `.env` file to add your API keys (or export them in your shell).
Non-secret gateway URLs, file roots, model categories, and model defaults belong
in `just-prompt.config.json`.

```
OPENAI_API_KEY=your_openai_api_key_here
MODEL_GATEWAY_API_KEY=your_gateway_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OLLAMA_HOST=http://localhost:11434
```

File-based tools are restricted to the server's current working directory by
default. Set `file_access_root` in `just-prompt.config.json` to allow reads and
writes inside a different directory. `JUST_PROMPT_FILE_ROOT` and
`--file-access-root` are runtime overrides.

When a model name is not found in a direct provider's model list, the legacy
multi-model tools (`prompt`, `prompt_from_file`, `ceo_and_board`) will use the
configured correction model to fuzzy-match it. This makes a live LLM call on
your behalf. Set `JUST_PROMPT_DISABLE_MODEL_CORRECTION=1` to disable it and use
model names as-is.

## Claude Code Installation
> In all these examples, replace the directory with the path to the just-prompt directory.

Default models are set in `just-prompt.config.json` unless you pass
`--default-models`. Prefer editing `default_models` in the config file for
normal use; keep the CLI flag for temporary overrides.

If you use Claude Code right out of the repository, `.mcp.json` only describes
how to launch the MCP server. Non-secret app settings live in
`just-prompt.config.json`; secrets live in `.env`.

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
        "just-prompt"
      ],
      "env": {}
    }
  }
}
```

The `default_models` config value sets the models to use when none are
explicitly provided to the API endpoints. The first model in the list is also
used for model name correction when needed. This can be a list of models
separated by commas. The `--default-models` CLI flag still exists as a temporary
override.

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
    "args": ["--directory", ".", "run", "just-prompt", "--default-models", "gateway:your-primary-model-id"]
}
```

With multiple default models:

```
{
    "command": "uv",
    "args": ["--directory", ".", "run", "just-prompt", "--default-models", "gateway:your-primary-model-id,gateway:your-review-model-id"]
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
  run just-prompt --default-models "gateway:your-primary-model-id"

# With multiple default models
claude mcp add just-prompt -s user \
  -- \
  uv --directory . \
  run just-prompt --default-models "gateway:your-primary-model-id,gateway:your-review-model-id"
```


## `mcp remove`

claude mcp remove just-prompt

## Running Tests

The unit test suite runs without any API keys:

```bash
uv run pytest
```

Tests that hit real provider APIs (OpenAI, Anthropic, Gemini, Groq, DeepSeek,
Ollama, or a configured gateway) are marked `live` and are skipped by default.
To include them, set the relevant API keys and run:

```bash
uv run pytest -m live
# or run everything:
uv run pytest -m "live or not live"
```

## Linting

```bash
uv run ruff check src/ scripts/
uv run ruff check --fix src/ scripts/   # apply safe auto-fixes
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
├── prompts/                   # Example prompt files
├── pyproject.toml             # Python project configuration
├── scripts/                   # Standalone utility scripts
│   └── list_models.py         # Script to list available LLM models
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
