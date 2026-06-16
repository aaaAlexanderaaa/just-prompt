"""
Tests for Gemini provider.

These tests hit the live Google Gemini API and are marked ``live``. Run the
default suite with ``-m "not live"`` to skip them.
"""

import os

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# All tests in this module exercise the real Gemini API.
pytestmark = pytest.mark.live

# Skip tests if API key not available
if not os.environ.get("GEMINI_API_KEY"):
    pytest.skip("Gemini API key not available", allow_module_level=True)


from just_prompt.atoms.llm_providers import gemini

# Cached model list so skipif decorators never hit the network at collection
# time (a live API failure there used to abort the whole pytest run).
_AVAILABLE_MODELS: list = []


def _available_models() -> list:
    if not _AVAILABLE_MODELS:
        try:
            _AVAILABLE_MODELS.extend(gemini.list_models())
        except Exception as exc:  # pragma: no cover - defensive
            pytest.skip(f"Gemini models unavailable in this environment: {exc}")
    return _AVAILABLE_MODELS


def test_list_models():
    """Test listing Gemini models."""
    models = gemini.list_models()

    # Assertions
    assert isinstance(models, list)
    assert len(models) > 0
    assert all(isinstance(model, str) for model in models)

    # Check for at least one expected model containing gemini
    gemini_models = [model for model in models if "gemini" in model.lower()]
    assert len(gemini_models) > 0, "No Gemini models found"


def test_prompt():
    """Test sending prompt to Gemini."""
    # Using gemini-1.5-flash as the model for testing
    response = gemini.prompt("What is the capital of France?", "gemini-1.5-flash")

    # Assertions
    assert isinstance(response, str)
    assert len(response) > 0
    assert "paris" in response.lower() or "Paris" in response


def test_parse_thinking_suffix():
    """Test parsing thinking suffix from model name."""
    # Test cases with valid formats
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:1k") == ("gemini-2.5-flash-preview-04-17", 1024)
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:4k") == ("gemini-2.5-flash-preview-04-17", 4096)
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:2048") == ("gemini-2.5-flash-preview-04-17", 2048)

    # Test cases with invalid models (should ignore suffix)
    assert gemini.parse_thinking_suffix("gemini-1.5-flash:4k") == ("gemini-1.5-flash", 0)

    # Test cases with invalid suffix format
    base_model, budget = gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:invalid")
    assert base_model == "gemini-2.5-flash-preview-04-17"
    assert budget == 0

    # Test case with no suffix
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17") == ("gemini-2.5-flash-preview-04-17", 0)

    # Test case with out-of-range values (should be clamped)
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:25000")[1] == 24576
    assert gemini.parse_thinking_suffix("gemini-2.5-flash-preview-04-17:-1000")[1] == 0


@pytest.mark.skipif(
    "gemini-2.5-flash-preview-04-17" not in _available_models(),
    reason="gemini-2.5-flash-preview-04-17 model not available"
)
def test_prompt_with_thinking():
    """Test sending prompt to Gemini with thinking enabled."""
    # Using the gemini-2.5-flash-preview-04-17 model with thinking budget
    model_name = "gemini-2.5-flash-preview-04-17:1k"
    response = gemini.prompt("What is the square root of 144?", model_name)

    # Assertions
    assert isinstance(response, str)
    assert len(response) > 0
    assert "12" in response.lower(), f"Expected '12' in response: {response}"


@pytest.mark.skipif(
    "gemini-2.5-flash-preview-04-17" not in _available_models(),
    reason="gemini-2.5-flash-preview-04-17 model not available"
)
def test_prompt_without_thinking():
    """Test sending prompt to Gemini without thinking enabled."""
    # Using the gemini-2.5-flash-preview-04-17 model without thinking budget
    model_name = "gemini-2.5-flash-preview-04-17"
    response = gemini.prompt("What is the capital of Germany?", model_name)

    # Assertions
    assert isinstance(response, str)
    assert len(response) > 0
    assert "berlin" in response.lower() or "Berlin" in response, f"Expected 'Berlin' in response: {response}"


@pytest.mark.live
def test_gemini_2_5_pro_availability():
    """Test if Gemini 2.5 Pro model is available (requires live API)."""
    # Validate against a live fetch, not a possible fallback list.
    models = _available_models()

    # Print all available models for debugging
    print("\nAvailable Gemini models:")
    for model in sorted(models):
        print(f"  - {model}")

    # Check if any Gemini 2.5 Pro variant is available
    gemini_2_5_pro_models = [model for model in models if "gemini-2.5-pro" in model.lower()]

    if gemini_2_5_pro_models:
        print(f"\nFound Gemini 2.5 Pro models: {gemini_2_5_pro_models}")
    else:
        print("\nNo Gemini 2.5 Pro models found!")
        print("You may need to update the google-genai library")

    # This assertion will fail if no Gemini 2.5 Pro is found
    assert len(gemini_2_5_pro_models) > 0, "Gemini 2.5 Pro model not found - may need to update google-genai library"
