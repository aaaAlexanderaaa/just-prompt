# Just Prompt - A lightweight MCP server for LLM providers

`just-prompt` is a Model Context Protocol (MCP) server that exposes LLMs as tools. It can call a configured OpenAI-compatible or multi-protocol model gateway, and still supports direct provider calls for OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, and Ollama. See how we use the `ceo_and_board` tool to make [hard decisions easy with o3 here](https://youtu.be/LEMLntjfihA).

<img src="images/just-prompt-logo.png" alt="Just Prompt Logo" width="700" height="auto">

<img src="images/o3-as-a-ceo.png" alt="Just Prompt Logo" width="700" height="auto">


## Tools

The core MCP tools are always available. Model-specific gateway tools such as
`grok_4_20_multi_agent_xhigh` are declared in `gateway_model_tools` inside
`just-prompt.config.json`; edit that list to add, remove, rename, or hide
model-as-tool entries without changing Python code.

The repository config currently exposes these tools:

- **`ask_model`**: Ask exactly one model through the configured gateway or a known provider prefix
  - Parameters:
    - `model`: Model ID. Unprefixed IDs are sent to the configured OpenAI-compatible gateway and use model metadata to auto-select a compatible protocol.
    - `prompt`: The prompt text
    - `options` (optional): Gateway options such as `protocol` (`auto` by default), `temperature`, `top_p`, `base_url`, `api_key`, `timeout`, and `payload` overrides. Omit `max_tokens` by default; it is a hard truncation cap, and `0` means uncapped/omitted.
  - Example:
    ```json
    {
      "model": "kimi-k2.7-code",
      "prompt": "Review this code. Here is the full relevant file content: ...",
      "options": { "timeout": 1200 }
    }
    ```
  - Timeout note: `options.timeout` is how long just-prompt waits for the gateway HTTP response. A backend may continue running after a client-side timeout. Some MCP clients also have their own tool-call timeout.
  - Context note: cloud models cannot read local files, repositories, terminal output, or previous tool results unless you include that content in the prompt or use `prompt_from_file`.

- **`mimo_v2_5_tts`**: Generate speech with `mimo-v2.5-tts`
  - Parameters:
    - `text` (required): Text to synthesize
    - `voice_id` (default: `male-qn-qingse`, used by speech protocols that accept one)
    - `output_path` (optional): Audio file path or output directory. Defaults to `generated/mimo-v2.5-tts-<utc>.mp3`
    - `payload` / `options` (optional): Raw payload overrides and gateway options. Uses assistant-role chat audio by default; pass `options.protocol` as `openai:audio-speech` or `minimax:t2a_v2` when your gateway supports those routes.
  - Output: JSON with `saved_audio_path` and `saved_audio_bytes`; URL audio responses are downloaded before the tool returns.

- **`minimax_speech_2_8_turbo`**: Generate speech with `minimax-speech-2.8-turbo`
  - Parameters are the same as `mimo_v2_5_tts`
  - Limitation: the integration test gateway returned `no_endpoints_available` for this model on 2026-06-06, so the tool is registered but may not be callable until the gateway exposes a live endpoint.

- **`minimax_m3_free`**: Ask `minimax-m3:free` through non-streaming OpenAI chat completions
  - Parameters:
    - `prompt` (required)
    - `system_prompt`, `temperature`, `max_tokens`, `top_p` (optional). Omit `max_tokens` unless you intentionally want truncation.
    - `payload` / `options` (optional)
  - Output: plain text from the model.

- **`gpt_image_2`**: Generate images with `gpt-image-2`
  - Parameters:
    - `prompt` (required)
    - `output_path` (optional): Image file path or output directory. Defaults to `generated/gpt-image-2-<utc>.png`
    - `size` (configured default, currently `4k`), `quality` (configured default, currently `auto`), `n` (configured default, currently `1`), `background`, `moderation`, `output_format` (configured default, currently `png`), `output_compression`
    - `payload` / `options` (optional)
  - Output: JSON with `saved_image_paths` and `saved_image_bytes`; URL image responses are downloaded before the tool returns.

- **`grok_4_20_multi_agent_xhigh`**: Ask the long-running, non-streaming search model `grok-4.20-multi-agent-xhigh`
  - Parameters:
    - `query` (required)
    - `system_prompt`, `temperature`, `max_tokens`, `top_p`, `search_parameters` (optional)
    - `payload` / `options` (optional)
  - Output: plain text from the model. Default timeout is longer than normal chat calls.
  - Caveat: this is internet research only, not local file search. Treat returned claims as evidence to verify against sources, not as absolute truth.

- **`prompt`**: Send a prompt to multiple LLM models
  - Parameters:
    - `text`: The prompt text
    - `models_prefixed_by_provider` (optional): List of models with provider prefixes. If not provided, uses default models.
    - `error_strategy` (optional): `{ "strategy": "best_effort" | "all_or_nothing" | "retry_with_backoff", "max_retries": 3, "backoff_seconds": 1 }`

- **`prompt_from_file`**: Send a prompt from a file to multiple LLM models
  - Parameters:
    - `abs_file_path`: Absolute path to an existing file inside the configured file access root. The default root is the just-prompt server's current working directory; set `JUST_PROMPT_FILE_ROOT` or `--file-access-root` when the file lives elsewhere.
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

Configure non-secret gateway settings in `just-prompt.config.json`:

```json
{
  "gateway": {
    "base_url": "https://your-gateway.example.com/v1"
  }
}
```

Keep the gateway API key in `.env` or your shell:

```bash
MODEL_GATEWAY_API_KEY=your_gateway_api_key
```

For gateways that need a separate non-`/v1` protocol root, add
`gateway.protocol_base_url` to `just-prompt.config.json`.

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

These tools use the shared `just-prompt.config.json` plus secrets from `.env` or
your shell. CLI calls and the MCP server read the same non-secret config.

Config file roles are intentionally narrow:

- `just-prompt.config.json`: shared non-secret runtime config for both CLI and MCP.
- `.env`: secrets and provider credentials only.
- `.mcp.json`: MCP client launch command only; no model defaults or gateway config.
- `pyproject.toml` and `uv.lock`: package/dependency metadata, not runtime config.

Media outputs are written inside the configured file root. By default that is
the MCP server's current working directory; set `JUST_PROMPT_FILE_ROOT` if you
want generated files under a different allowed directory. If `output_path` is
omitted, files are saved under `generated/`. If `output_path` points to a
directory such as `./`, the tool creates a timestamped filename inside it.

Model-as-tool entries are declarative. Add an entry under
`gateway_model_tools` to expose a gateway model as an MCP tool:

```json
{
  "gateway_model_tools": [
    {
      "name": "deep_research",
      "model": "grok-4.20-multi-agent-xhigh",
      "category": "search",
      "description": "Run long-form research through the configured gateway.",
      "enabled": true
    }
  ]
}
```

Supported categories are `text`, `speech`, `image`, and `search`. The category
selects the MCP input schema and runtime adapter. Set `enabled` to `false` to
hide a configured tool without deleting it. Tool names cannot override core
tools such as `ask_model`, `prompt`, or `list_gateway_models`.

General model-call rules for agents:

- Pass all required context explicitly. A cloud model cannot inspect local files
  or workspace state just because just-prompt is running locally.
- Do not set `max_tokens` by habit. It is a hard truncation cap; omit it for the
  broadest output, or pass `0` to have just-prompt treat it as omitted.
- For slow models, set `options.timeout` high enough for the task. `ask_model`
  defaults to a 900 second gateway wait, search tools default to 1200 seconds,
  and some MCP clients may still enforce a separate tool-call timeout.

Model defaults are configurable in `just-prompt.config.json`. The project reads
that file by default, then merges `JUST_PROMPT_CONFIG_FILE` and
`JUST_PROMPT_CONFIG` if they are set. Defaults merge in this order:

- code fallback
- category defaults such as `image`
- model defaults such as `gpt-image-2`
- explicit MCP/CLI arguments

Example config file:

```json
{
  "gateway": {
    "base_url": "https://tokendance.space/gateway/v1"
  },
  "gateway_model_tools": [
    {
      "name": "gpt_image_2",
      "model": "gpt-image-2",
      "category": "image",
      "description": "Generate an image with the gateway model gpt-image-2."
    },
    {
      "name": "grok_4_20_multi_agent_xhigh",
      "model": "grok-4.20-multi-agent-xhigh",
      "category": "search",
      "description": "Run long-form research through the configured gateway."
    }
  ],
  "model_categories": {
    "your-custom-image-model": "image"
  },
  "model_defaults": {
    "categories": {
      "text": {
        "timeout": 900,
        "max_tokens": 0
      },
      "image": {
        "size": "4k",
        "quality": "auto",
        "n": 1,
        "output_format": "png"
      },
      "search": {
        "timeout": 1200,
        "max_tokens": 0
      }
    },
    "models": {
      "gpt-image-2": {
        "size": "4k"
      },
      "grok-4.20-multi-agent-xhigh": {
        "system_prompt": "Prefer primary sources, include concrete publication dates, and separate verified facts from inference.",
        "timeout": 1200,
        "query_template": "Perform deep research on {topic}."
      }
    }
  }
}
```

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

- `size`: `4k` from `just-prompt.config.json`
- `quality`: `auto`
- `n`: `1`
- `output_format`: `png`
- `output_path`: `generated/gpt-image-2-<utc>.png`
- gateway timeout: `900` seconds
- media URL download timeout: `120` seconds

Accepted parameters:

- `size`: configured default is `4k` in this project, or another value accepted by the gateway/model.
- `quality`: configured default is `auto`, or another explicit quality value accepted by the gateway/model.
- `n`: number of images. Default is `1`.
- `background`, `moderation`, `output_format`, `output_compression`
- `payload`: raw image-generation overrides.
- `options`: `api_key`, `base_url`, `timeout`, `media_download_timeout`.

Output contract:

- The tool finishes only after it saves local image files.
- It handles base64/data responses and HTTP(S) image URLs.
- Returned JSON includes `saved_image_paths` and `saved_image_bytes`; when the gateway returned a URL, it is retained as `source_image_urls` for traceability.

Prompt-only configured-defaults call:

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

On this gateway, examples keep `quality` at `auto` and use the configured image
size default. Override those fields only when the task itself requires a
specific setting.

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
`grok-4.20-multi-agent-xhigh` through OpenAI chat completions. This tool is a
`gateway_model_tools` declaration with category `search`, so you can remove,
rename, disable, or replace it from `just-prompt.config.json`. This is the
first-layer deep-research tool — Chinese community on linux.do calls it
"传奇搜索大王". It is especially strong for real-time X data plus academic
paper, policy, official report, and market synthesis. Use it before Exa,
Bocha, or default web search when current external evidence quality matters.

Important caveat: this tool is powerful because it can search broader internet
source surfaces and run richer multi-step research. Its final summarizer is
still an AI model, not an oracle. Treat returned claims as evidence to verify
against cited sources, not as absolute truth. It also cannot search local files
or private workspace state; paste local context into the query/payload when it
matters.

Recommended fallback chain when this model is unreachable or times out:
`grok_4_20_multi_agent_xhigh` -> Exa -> Bocha -> default web search.

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

Best practice: precisely define scope and depth; specify required research
dimensions, data freshness, and source quality. Force structured output such
as Executive Summary, Findings with inline citations, Agent Debate Highlights,
Uncertainties/Gaps, Sources, and Recommendations. Prefer English prompts for
stronger consistency. Ask for source URLs, publication dates, primary evidence,
and uncertainty notes whenever factual accuracy matters.

Recommended `system_prompt`:

```
Prefer primary sources, include concrete publication dates, and separate verified facts from inference.
```

Recommended deep-research query template (configured under
`model_defaults.models.grok-4.20-multi-agent-xhigh.query_template` in this
repository and also shipped at `prompts/grok_deep_research.txt` for
`prompt_from_file` reuse):

```
Perform a comprehensive 16-agent Realtime Multi-Agent Deep Research in xhigh mode on [主题]. Leave no stone unturned.

Harper team: be exhaustive with web, X (use advanced operators for latest posts), academic papers, official reports.
Benjamin: verify all technical/financial/logical claims.
Lucas: ruthlessly challenge assumptions and explore contrarian scenarios.

Follow strict process: decompose -> parallel research -> multiple rounds of debate -> consensus synthesis.

Deliver a professional-grade report equivalent to a top consulting firm team working for days. Structure: Executive Summary, Detailed Analysis (use tables for comparisons), Counterarguments & Limitations, Actionable Insights, Complete References with links where available.
```

Output contract: synthesized research text. The response may include
citations, source names, dates, or caveats depending on gateway output. It
is not streaming; wait for the full result. Treat timeouts or gateway
errors as a reason to fall back to the next search provider.

Minimal call:

```json
{
  "query": "Find recent privacy-minded local AI tooling for home lab operators. Give three concise bullets with dates.",
  "system_prompt": "Prefer primary sources, include concrete publication dates, and separate verified facts from inference."
}
```

## One-Shot CLI Calls

`just-prompt` still starts the MCP stdio server by default. For direct shell
usage, use the `call` subcommand:

```bash
uv run just-prompt call MODEL [--category text|speech|image|search] [adapter options] [input]
```

The CLI chooses an adapter in this order:

- If `--category` is provided, use that adapter.
- If the model is in `model_categories` or the built-in mapping, use the mapped
  adapter.
- Otherwise, default to the `text` adapter.

Built-in model mappings:

- `mimo-v2.5-tts`: `speech`
- `minimax-speech-2.8-turbo`: `speech`
- `minimax-m3:free`: `text`
- `gpt-image-2`: `image`
- `grok-4.20-multi-agent-xhigh`: `search`

Add or override mappings in `just-prompt.config.json` under `model_categories`.

MCP tool-style aliases such as `gpt_image_2` are accepted and normalized to the
real model ID.

To inspect the accepted parameters and defaults for the resolved adapter, ask
for help after the model name:

```bash
uv run just-prompt call gpt-image-2 --help
uv run just-prompt call some-new-image-model --category image --help
uv run just-prompt call unknown-chat-model --help
```

Examples:

```bash
uv run just-prompt call minimax-m3:free "给我三条家庭知识库整理建议。"
```

```bash
uv run just-prompt call gpt-image-2 "A crisp square illustration of a compact home lab desk, warm morning light, no text."
```

```bash
uv run just-prompt call mimo-v2.5-tts --text "请用自然旁白语气朗读这段家庭档案说明。"
```

```bash
uv run just-prompt call grok-4.20-multi-agent-xhigh --query "Find recent privacy-minded local AI tooling for home lab operators. Give three concise bullets with dates."
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
- Generation: `--size` (project default `4k`), `--quality` (default `auto`), `--n` (default `1`), `--background`, `--moderation`, `--output-format`, `--output-compression`.
- Gateway: `--base-url`, `--api-key`, `--timeout`, `--media-download-timeout`, `--payload`, `--options`.
- The command returns only after image data or image URLs have been saved as local files.

Search adapter parameters:

- Primary input: positional input, `--query`, `--query-file`, or stdin.
- Optional: `--system-prompt`, `--system-prompt-file`, `--temperature`, `--top-p`, `--max-tokens`, `--search-parameters`.
- Gateway: `--base-url`, `--api-key`, `--timeout`, `--payload`, `--options`.
- `--max-tokens` is a hard output-length cap; omit it for normal full-answer behavior.

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

Default models are set in `just-prompt.config.json` (`gateway:glm-4.7` in this
project) unless you pass `--default-models`.

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
