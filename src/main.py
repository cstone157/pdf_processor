import os
import sys
import argparse
import logging

import pdfplumber

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

def load_environment():
    """
    Loads and validates environment variables.
    """
    load_dotenv()
    
    required_vars = ["OPENAI_ENDPOINT", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_API_VERSION"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file.")
        sys.exit(1)

def load_system_prompt(filename):
    """Loads the agent behavior definition from a markdown file."""
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: Could not find {filename}. Please create it in the same directory.")
        sys.exit(1)


def main(file_path, start_page=0, num_pages=100):
    """
    Main function to take the requested file.  Break the file into blocks, and pass them to the
    LLM to write python code to process the data into a structured format for storing the data in
    a vector database.  The LLM will return the code to process the data, and the code will be executed
    Args:
        file_path (str): Path to the PDF file to be processed.
        start_page (int): The page number to start processing from.
        num_pages (int): The number of pages to process.
    """
    pdf_script_tool_prompt = load_system_prompt("agents/pdf_script_gen/AGENTS.md")
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
        api_key=os.getenv("OPENAI_API_KEY"),
        azure_deployment=os.getenv("OPENAI_MODEL"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        temperature=0.7
    )

    chat_history = [
        SystemMessage(content=pdf_script_tool_prompt)
    ]

    logger.info("="*50)
    logger.info("🤖 PDF Script Generation Agent Initialized")
    logger.info("="*50)

    reader = pdfplumber.open(file_path)
    for page_number in range(start_page, min(start_page + num_pages, len(reader.pages))):
        page = reader.pages[page_number]
        text = page.extract_text()
        logger.info("="*50)
        logger.info(f"\n\nPage {page_number}:\n{text}\n\n")
        chat_history.append(HumanMessage(content=text))
        response = llm.invoke(chat_history)
        chat_history.append(AIMessage(content=response.content))
        logger.info(f"Response from LLM for page {page_number}:\n{response.content}\n\n")


if __name__ == "__main__":
    # Set up argument parser for command-line arguments
    parser = argparse.ArgumentParser(description="Process PDF by block headers (e.g., 3.6.14).")
    parser.add_argument("path", help="Path to the PDF file")
    parser.add_argument("-s", "--start_page", type=int, default=-1, help="Start page number (1-indexed)")
    parser.add_argument("-n", "--pages", type=int, default=100, help="Number of pages")
    parser.add_argument("-l", "--log", action="store_true", help="Enable logging to a file")
    parser.add_argument("-lf", "--log_file", type=str, default="example.log", help="Log file name (default: example.log)")
    parser.add_argument("-lv", "--log_level", type=str, default="INFO", help="Log level (default: INFO)")
    args = parser.parse_args()

    # Set up logging based on command-line arguments
    if args.log:
        logging.basicConfig(filename=args.log_file, encoding='utf-8', level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')

    if os.path.exists(args.path):
        # Load environment variables and validate them
        load_environment()
        # Call the main function with the provided arguments
        main(args.path, start_page=args.start_page, num_pages=args.pages)
    else:
        logger.error(f"File {args.path} does not exist.")