"""
Data types and models for just-prompt MCP server.
"""

from enum import Enum


class ModelProviders(Enum):
    """
    Enum of supported model providers with their full and short names.
    """
    OPENAI = ("openai", "o")
    ANTHROPIC = ("anthropic", "a")
    GEMINI = ("gemini", "g")
    GROQ = ("groq", "q")
    DEEPSEEK = ("deepseek", "d")
    OLLAMA = ("ollama", "l")
    GATEWAY = ("gateway", "gw", ("openai-compatible", "oc", "llm"))

    def __init__(self, full_name, short_name, aliases=()):
        self.full_name = full_name
        self.short_name = short_name
        self.aliases = aliases

    @classmethod
    def from_name(cls, name):
        """
        Get provider enum from full or short name.
        
        Args:
            name: The provider name (full or short)
            
        Returns:
            ModelProviders: The corresponding provider enum, or None if not found
        """
        normalized = name.strip().lower()
        for provider in cls:
            if (
                provider.full_name == normalized
                or provider.short_name == normalized
                or normalized in provider.aliases
            ):
                return provider
        return None
