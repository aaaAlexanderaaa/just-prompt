"""
DeepSeek provider implementation.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

client: OpenAI | None = None


def _get_client() -> OpenAI:
    global client
    if client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("Missing DEEPSEEK_API_KEY for the DeepSeek provider.")
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return client


def prompt(text: str, model: str) -> str:
    """
    Send a prompt to DeepSeek and get a response.
    
    Args:
        text: The prompt text
        model: The model name
        
    Returns:
        Response string from the model
    """
    try:
        logger.info(f"Sending prompt to DeepSeek model: {model}")

        # Create chat completion
        response = _get_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": text}],
            stream=False,
        )

        # Extract response content
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error sending prompt to DeepSeek: {e}")
        raise ValueError(f"Failed to get response from DeepSeek: {str(e)}") from e


def list_models() -> list[str]:
    """
    List available DeepSeek models.
    
    Returns:
        List of model names
    """
    try:
        logger.info("Listing DeepSeek models")
        response = _get_client().models.list()

        # Extract model IDs
        models = [model.id for model in response.data]

        return models
    except Exception as e:
        logger.error(f"Error listing DeepSeek models: {e}")
        # Return some known models if API fails
        logger.info("Returning hardcoded list of known DeepSeek models")
        return [
            "deepseek-coder",
            "deepseek-chat",
            "deepseek-reasoner",
            "deepseek-coder-v2",
            "deepseek-reasoner-lite"
        ]
