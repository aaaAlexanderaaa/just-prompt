"""
Prompt functionality for just-prompt.
"""

import concurrent.futures
import logging
import os
import time
from typing import Any

from ..atoms.shared.data_types import ModelProviders
from ..atoms.shared.model_router import ModelRouter, model_correction_disabled
from ..atoms.shared.utils import DEFAULT_MODEL, split_provider_and_model
from ..atoms.shared.validator import validate_models_prefixed_by_provider

logger = logging.getLogger(__name__)


def _error_strategy_config(error_strategy: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize error handling options while preserving the old best-effort default.
    """
    config = dict(error_strategy or {})
    strategy = str(config.get("strategy") or os.environ.get("ERROR_STRATEGY") or "best_effort")
    strategy = strategy.strip().lower().replace("-", "_")

    if strategy not in {"best_effort", "all_or_nothing", "retry_with_backoff"}:
        raise ValueError(
            "error_strategy.strategy must be one of: best_effort, all_or_nothing, retry_with_backoff"
        )

    max_retries = int(config.get("max_retries", os.environ.get("MAX_RETRIES", 0)))
    if strategy == "retry_with_backoff" and max_retries < 1:
        max_retries = 3

    return {
        "strategy": strategy,
        "max_retries": max(0, max_retries),
        "backoff_seconds": float(config.get("backoff_seconds", os.environ.get("BASE_DELAY", 1.0))),
    }


def _process_model_prompt(
    model_string: str,
    text: str,
    *,
    max_retries: int = 0,
    backoff_seconds: float = 1.0,
    raise_on_error: bool = False,
) -> str:
    """
    Process a single model prompt.
    
    Args:
        model_string: String in format "provider:model"
        text: The prompt text
        
    Returns:
        Response from the model
    """
    attempt = 0
    while True:
        try:
            return ModelRouter.route_prompt(model_string, text)
        except Exception as e:
            logger.error(f"Error processing prompt for {model_string}: {e}")
            if attempt >= max_retries:
                if raise_on_error:
                    raise
                return f"Error ({model_string}): {str(e)}"

            delay = backoff_seconds * (2 ** attempt)
            logger.info("Retrying %s after %.2fs", model_string, delay)
            time.sleep(delay)
            attempt += 1


def _correct_model_name(provider: str, model: str, correction_model: str) -> str:
    """
    Correct a model name using the correction model.
    
    Args:
        provider: Provider name
        model: Model name
        correction_model: Model to use for correction
        
    Returns:
        Corrected model name
    """
    try:
        provider_enum = ModelProviders.from_name(provider)
        if provider_enum and provider_enum.full_name == "gateway":
            return model
        if model_correction_disabled():
            logger.debug(
                "Model correction disabled; using '%s' as-is for %s",
                model,
                provider,
            )
            return model
        return ModelRouter.magic_model_correction(provider, model, correction_model)
    except Exception as e:
        logger.error(f"Error correcting model name {provider}:{model}: {e}")
        return model


def prompt(
    text: str,
    models_prefixed_by_provider: list[str] = None,
    error_strategy: dict[str, Any] | None = None,
) -> list[str]:
    """
    Send a prompt to multiple models using parallel processing.
    
    Args:
        text: The prompt text
        models_prefixed_by_provider: List of model strings in format "provider:model"
                                    If None, uses the DEFAULT_MODELS environment variable
        error_strategy: Optional object with strategy, max_retries, and backoff_seconds
        
    Returns:
        List of responses from the models
    """
    # Use default models if no models provided
    if not models_prefixed_by_provider:
        default_models = os.environ.get("DEFAULT_MODELS", DEFAULT_MODEL)
        models_prefixed_by_provider = [model.strip() for model in default_models.split(",")]
    # Validate model strings
    validate_models_prefixed_by_provider(models_prefixed_by_provider)
    strategy_config = _error_strategy_config(error_strategy)

    # Prepare corrected model strings
    corrected_models = []
    for model_string in models_prefixed_by_provider:
        provider, model = split_provider_and_model(model_string)

        # Get correction model from environment
        correction_model = os.environ.get("CORRECTION_MODEL", DEFAULT_MODEL)

        # Check if model needs correction
        corrected_model = _correct_model_name(provider, model, correction_model)

        # Use corrected model
        if corrected_model != model:
            model_string = f"{provider}:{corrected_model}"

        corrected_models.append(model_string)

    # Process each model in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks, preserving submission order.
        futures = [
            executor.submit(
                _process_model_prompt,
                model_string,
                text,
                max_retries=strategy_config["max_retries"],
                backoff_seconds=strategy_config["backoff_seconds"],
                raise_on_error=strategy_config["strategy"] == "all_or_nothing",
            )
            for model_string in corrected_models
        ]

        if strategy_config["strategy"] == "all_or_nothing":
            # Surface the first failure as soon as it happens. In-flight tasks
            # in a ThreadPoolExecutor cannot truly be cancelled, so we don't
            # pretend otherwise; we just stop waiting and propagate the error.
            for future in concurrent.futures.as_completed(futures):
                future.result()
            # All succeeded; fall through to ordered collection below.

        # Collect results in submission order.
        responses = [future.result() for future in futures]

    return responses
