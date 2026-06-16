"""
Single-model Model-as-Tool helper.
"""

from typing import Any

from ..atoms.llm_providers import gateway
from ..atoms.shared.data_types import ModelProviders
from ..atoms.shared.model_router import ModelRouter
from ..atoms.shared.utils import split_provider_and_model


def _known_provider_model(model: str) -> bool:
    if ":" not in model:
        return False
    prefix, _ = split_provider_and_model(model)
    return ModelProviders.from_name(prefix) is not None


def ask_model(model: str, prompt: str, options: dict[str, Any] | None = None) -> str:
    """
    Ask exactly one model and return the text result.

    Unprefixed model IDs are sent to the configured OpenAI-compatible gateway.
    Existing provider-prefixed IDs keep the historical provider routing.
    """
    if _known_provider_model(model):
        provider, model_name = split_provider_and_model(model)
        provider_enum = ModelProviders.from_name(provider)
        if provider_enum and provider_enum.full_name == "gateway":
            return gateway.prompt(prompt, model_name, options=options)
        return ModelRouter.route_prompt(model, prompt)

    return gateway.prompt(prompt, model, options=options)


def call_model_protocol(
    model: str,
    protocol: str,
    payload: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> Any:
    """
    Call a documented gateway protocol endpoint for any compatible model.
    """
    return gateway.call_protocol(model, protocol, payload=payload, options=options)


def get_model_task(protocol: str, task_id: str, options: dict[str, Any] | None = None) -> Any:
    """
    Poll an async model task for protocols that publish task endpoints.
    """
    return gateway.get_task(protocol, task_id, options=options)


def list_gateway_model_details():
    """
    Return model metadata from the configured gateway.
    """
    return gateway.list_model_details()
