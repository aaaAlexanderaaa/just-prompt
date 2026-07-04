"""
Tests for the one-shot CLI adapter layer.
"""

from io import StringIO

from just_prompt import cli


def test_cli_infers_mapped_category_and_defaults_to_text():
    assert cli.infer_model_category("gpt-image-2") == "image"
    assert cli.infer_model_category("gw:gpt-image-2") == "image"
    assert cli.infer_model_category("unknown-model") == "text"
    assert cli._gateway_model_id("gpt_image_2") == "gpt-image-2"


def test_cli_infers_category_from_declarative_gateway_tool(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "just-prompt.config.json").write_text(
        """
        {
          "gateway_model_tools": [
            {
              "name": "deep_research",
              "model": "custom-search-model",
              "category": "search"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    assert cli.infer_model_category("custom-search-model") == "search"


def test_cli_model_help_uses_inferred_image_adapter():
    stdout = StringIO()

    code = cli.run(["call", "gpt-image-2", "--help"], stdout=stdout)

    output = stdout.getvalue()
    assert code == 0
    assert "image adapter" in output
    assert "--quality QUALITY" in output
    assert "(default: 4k)" in output
    assert "(default: auto)" in output
    assert "resolved category: image (mapped)" in output


def test_cli_unknown_model_defaults_to_text_adapter(monkeypatch):
    calls = {}

    def fake_chat_model(model, **kwargs):
        calls["model"] = model
        calls.update(kwargs)
        return "text answer"

    monkeypatch.setattr(cli.gateway_model_tools, "ask_gateway_chat_model", fake_chat_model)
    stdout = StringIO()

    code = cli.run(
        ["call", "unknown-model", "hello", "world", "--temperature", "0.2"],
        stdout=stdout,
    )

    assert code == 0
    assert stdout.getvalue().strip() == "text answer"
    assert calls["model"] == "unknown-model"
    assert calls["prompt"] == "hello world"
    assert calls["temperature"] == 0.2
    assert calls["options"]["timeout"] == 900.0


def test_cli_category_override_uses_requested_adapter(monkeypatch):
    calls = {}

    def fake_image_model(model, **kwargs):
        calls["model"] = model
        calls.update(kwargs)
        return '{"saved_image_paths": ["/tmp/image.png"]}'

    monkeypatch.setattr(cli.gateway_model_tools, "generate_openai_image", fake_image_model)
    stdout = StringIO()

    code = cli.run(
        [
            "call",
            "minimax-m3:free",
            "--category",
            "image",
            "--prompt",
            "A polished square diagram, no text.",
        ],
        stdout=stdout,
    )

    assert code == 0
    assert "saved_image_paths" in stdout.getvalue()
    assert calls["model"] == "minimax-m3:free"
    assert calls["prompt"] == "A polished square diagram, no text."
    assert calls["quality"] == "auto"
    assert calls["size"] == "4k"


def test_cli_loads_config_env_defaults_without_overriding_shell_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MODEL_GATEWAY_BASE_URL", raising=False)
    monkeypatch.setenv("MODEL_GATEWAY_API_KEY", "shell-key")
    (tmp_path / "just-prompt.config.json").write_text(
        """
        {
          "gateway": {
            "base_url": "https://gateway.example.test/v1"
          }
        }
        """,
        encoding="utf-8",
    )

    cli.apply_config_env_defaults()

    assert cli.os.environ["MODEL_GATEWAY_BASE_URL"] == "https://gateway.example.test/v1"
    assert cli.os.environ["MODEL_GATEWAY_API_KEY"] == "shell-key"


def test_server_help_uses_configured_default_models(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "just-prompt.config.json").write_text(
        '{"default_models": "gateway:configured-model"}',
        encoding="utf-8",
    )

    parser = cli._build_server_parser("just-prompt")

    assert parser.get_default("default_models") == "gateway:configured-model"
