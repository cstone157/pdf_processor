import os
import re
import json
import logging

import pdfplumber
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from utils import load_system_prompts, load_environment, load_arguments


class PdfParseState(TypedDict):
    """
    """
    text: str


logger = logging.getLogger(__name__)
load_environment()                      # Load and validate environment variables
args = load_arguments()                 # Set up argument parser for command-line arguments


if __name__ == "__main__":
    # Set up logging based on command-line arguments
    if args.log:
        logging.basicConfig(filename=args.log_file, encoding='utf-8', level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')

    if os.path.exists(args.path):
        # Initialize the PDF reader
        reader = pdfplumber.open(args.path)

        # Initialize the LLM with Azure OpenAI settings
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
            api_key=os.getenv("OPENAI_API_KEY"),
            azure_deployment=os.getenv("OPENAI_MODEL"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            temperature=0.7
        )

        # Retrieve our system prompts from the prompts directory
        statement_dict = load_system_prompts()
        statement = statement_dict.get("page_scan")

        messages = [
            SystemMessage(content=statement),
            HumanMessage(content="")
        ]


        logger.info(f"Processing file: {args.path}")

        for i in range(10, 20):  # Process pages 10 to 19
            logger.info(f"Processing page {i + 1} of {len(reader.pages)}")

            # Invoke the LLM to process the current page
            page = reader.pages[i]
            messages[1] = HumanMessage(content=page.extract_text())
            response = llm.invoke(messages)

            logger.info(f"LLM response for page {i + 1}: \n{response}\n\n")

    else:
        logger.error(f"File {args.path} does not exist.")
