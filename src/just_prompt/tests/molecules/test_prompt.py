"""
Tests for prompt functionality.
"""

import os
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from just_prompt.molecules.prompt import prompt

# Load environment variables
load_dotenv()


def test_prompt_disable_model_correction_skips_magic_correction(monkeypatch):
    """The opt-out must prevent the legacy pre-correction path from calling an LLM."""
    monkeypatch.setenv("JUST_PROMPT_DISABLE_MODEL_CORRECTION", "1")

    with (
        patch(
            "just_prompt.molecules.prompt.ModelRouter.magic_model_correction",
            return_value="corrected-model",
        ) as mock_correction,
        patch(
            "just_prompt.molecules.prompt.ModelRouter.route_prompt",
            return_value="ok",
        ) as mock_route_prompt,
    ):
        response = prompt("hello", ["openai:typo-model"])

    assert response == ["ok"]
    mock_correction.assert_not_called()
    mock_route_prompt.assert_called_once_with("openai:typo-model", "hello")


def test_prompt_preserves_duplicate_model_results(monkeypatch):
    """Duplicate model entries should keep distinct futures and ordered results."""
    monkeypatch.setenv("JUST_PROMPT_DISABLE_MODEL_CORRECTION", "1")

    class FakeFuture:
        def __init__(self, value):
            self.value = value

        def result(self):
            return self.value

    class FakeExecutor:
        def __init__(self):
            self.futures = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def submit(self, fn, model_string, text, **kwargs):
            future = FakeFuture(f"{len(self.futures)}:{model_string}")
            self.futures.append(future)
            return future

    executor = FakeExecutor()

    with patch(
        "just_prompt.molecules.prompt.concurrent.futures.ThreadPoolExecutor",
        return_value=executor,
    ):
        response = prompt(
            "hello",
            ["openai:duplicate-model", "openai:duplicate-model"],
        )

    assert response == [
        "0:openai:duplicate-model",
        "1:openai:duplicate-model",
    ]


@pytest.mark.live
def test_prompt_basic():
    """Test basic prompt functionality with a real API call."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not available")

    # Define a simple test case
    test_prompt = "What is the capital of France?"
    test_models = ["openai:gpt-4o-mini"]

    # Call the prompt function with a real model
    response = prompt(test_prompt, test_models)

    # Assertions
    assert isinstance(response, list)
    assert len(response) == 1
    assert "paris" in response[0].lower() or "Paris" in response[0]

@pytest.mark.live
def test_prompt_multiple_models():
    """Test prompt with multiple models."""
    # Skip if API keys aren't available
    if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Required API keys not available")

    # Define a simple test case
    test_prompt = "What is the capital of France?"
    test_models = ["openai:gpt-4o-mini", "anthropic:claude-3-5-haiku-20241022"]

    # Call the prompt function with multiple models
    response = prompt(test_prompt, test_models)

    # Assertions
    assert isinstance(response, list)
    assert len(response) == 2
    # Check all responses contain Paris
    for r in response:
        assert "paris" in r.lower() or "Paris" in r
