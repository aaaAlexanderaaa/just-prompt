"""
List providers functionality for just-prompt.
"""

import logging

from ..atoms.shared.data_types import ModelProviders

logger = logging.getLogger(__name__)


def list_providers() -> list[dict[str, str]]:
    """
    List all available providers with their full and short names.
    
    Returns:
        List of dictionaries with provider information
    """
    providers = []
    for provider in ModelProviders:
        providers.append({
            "name": provider.name,
            "full_name": provider.full_name,
            "short_name": provider.short_name,
            "aliases": ", ".join(provider.aliases)
        })

    return providers
