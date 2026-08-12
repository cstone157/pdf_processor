import os
import sys
import logging
import argparse

from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_system_prompts(agents_folder: str) -> dict:
    """
    Loads the agent behavior definition from a markdown file.
    """
    to_return = {}
    try:
        directories = [x for x in Path(f"./{agents_folder}").iterdir() if x.is_dir()]
        for directory in directories:
            agent_file = directory / "AGENTS.md"
            if agent_file.exists():
                with open(agent_file, "r", encoding="utf-8") as file:
                    dir_name = directory.name
                    to_return[dir_name] = file.read()
    except Exception as e:
        logger.error(f"Error loading system prompts: {e}")
        sys.exit(1)
    return to_return


def load_environment():
    """
    Loads and validates environment variables.
    Args:
        None
    """
    load_dotenv()
    required_vars = ["OPENAI_ENDPOINT", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_API_VERSION"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file.")
        sys.exit(1)


def load_arguments():
    """
    Sets up command-line arguments for the script.
    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Process PDF by block headers (e.g., 3.6.14).")
    parser.add_argument("path", help="Path to the PDF file")
    parser.add_argument("-s", "--start_page", type=int, default=0, help="Start page number (0-indexed)")
    parser.add_argument("-n", "--pages", type=int, default=100, help="Number of pages")
    parser.add_argument("-l", "--log", action="store_true", help="Enable logging to a file")
    parser.add_argument("-lf", "--log_file", type=str, default="example.log", help="Log file name (default: example.log)")
    parser.add_argument("-lv", "--log_level", type=str, default="INFO", help="Log level (default: INFO)")

    return parser.parse_args()