"""
Main entry point for just-prompt.
"""

import argparse
import asyncio
import logging
import sys
from dotenv import load_dotenv
from .server import serve
from .atoms.shared.utils import DEFAULT_MODEL
from .atoms.shared.validator import print_provider_availability

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main entry point for just-prompt.
    """
    parser = argparse.ArgumentParser(description="just-prompt - A lightweight MCP server for various LLM providers")
    parser.add_argument(
        "--default-models", 
        default=DEFAULT_MODEL,
        help="Comma-separated list of default models to use for prompts and model name correction, in format provider:model"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--show-providers",
        action="store_true",
        help="Show available providers and exit"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Show provider availability and optionally exit
    if args.show_providers:
        print_provider_availability()
        sys.exit(0)
    
    try:
        # Start server (asyncio)
        asyncio.run(serve(args.default_models))
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
