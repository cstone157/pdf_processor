import os
import re
import logging

import pdfplumber

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from utils import load_system_prompts, load_environment, load_arguments

logger = logging.getLogger(__name__)

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
    prompts = load_system_prompts("agents")
    logger.info(f"Loaded system prompts: {list(prompts.keys())}")
    logger.info("="*50)

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
        api_key=os.getenv("OPENAI_API_KEY"),
        azure_deployment=os.getenv("OPENAI_MODEL"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        temperature=0.7
    )

    # chat_history = [
    #     SystemMessage(content=prompts['pdf_script_gen'])
    # ]

    logger.info("🤖 PDF Script Generation Agent Initialized")
    logger.info("="*50)

    text = ""
    reader = pdfplumber.open(file_path)
    for page_number in range(start_page, min(start_page + num_pages, len(reader.pages))):
        page = reader.pages[page_number]
        # text = page.extract_text()
        text += page.extract_text()

        # logger.info("="*50)
        # logger.info(f"\n\nPage {page_number}:\n{text}\n\n")
        # chat_history.append(HumanMessage(content=text))
        # response = llm.invoke(chat_history)
        # chat_history.append(AIMessage(content=response.content))
        # logger.info(f"Response from LLM for page {page_number}:\n{response.content}\n\n")
    
    parts = re.split(r'(\n\d+\.\s[A-Z\s]+(?:\n|$))', text)
    logger.info(f"Total parts extracted: {len(parts)}")
    logger.info("="*50)

    fixed_parts = []
    tmp_part = ""
    for part in parts:
        if re.match(r'\n\d+\.\s[A-Z\s]+(?:\n|$)', part):
            if tmp_part:
                fixed_parts.append(tmp_part)
            tmp_part = part
        else:
            tmp_part += part
    if tmp_part:
        fixed_parts.append(tmp_part)

    # for fixed_part in fixed_parts:
    #     logger.info("="*50)
    #     logger.info(f"{fixed_part}\n\n")

    # Attempting to use the LLM to process and extract the table of contents
    logger.info("="*50)
    logger.info("Attempting to extract table of contents using LLM...")
    chat_history = [
        SystemMessage(content=prompts['pdf_table_of_contents']),
        HumanMessage(content=fixed_parts[0])
    ]
    response = llm.invoke(chat_history)
    logger.info(f"Response from LLM for table of contents:\n{response.content}\n\n")



if __name__ == "__main__":
    # Set up argument parser for command-line arguments
    args = load_arguments()

    # Set up logging based on command-line arguments
    if args.log:
        logging.basicConfig(filename=args.log_file, encoding='utf-8', level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')

    if os.path.exists(args.path):
        load_environment()
        main(args.path, start_page=args.start_page, num_pages=args.pages)
    else:
        logger.error(f"File {args.path} does not exist.")