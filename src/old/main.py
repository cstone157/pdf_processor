import os
import re
import argparse
import chromadb
import pdfplumber
import nltk
import logging
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist

from old.DocPdfParser import DocPdfParser

chroma_client = chromadb.PersistentClient(path="./chroma_db")
logger = logging.getLogger(__name__)

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF by block headers (e.g., 3.6.14).")
    parser.add_argument("path", help="Path to the PDF file")
    parser.add_argument("-s", "--start_page", type=int, default=-1, help="Start page number (1-indexed)")
    parser.add_argument("-n", "--pages", type=int, default=100, help="Number of pages")
    parser.add_argument("-l", "--log", action="store_true", help="Enable logging to a file")
    parser.add_argument("-lf", "--log_file", type=str, default="example.log", help="Log file name (default: example.log)")
    parser.add_argument("-lv", "--log_level", type=str, default="INFO", help="Log level (default: INFO)")
    args = parser.parse_args()

    if args.log:
        logging.basicConfig(filename=args.log_file, encoding='utf-8', level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
        
    if os.path.exists(args.path):
        parser = DocPdfParser(args.path)

        # Determine Title and Collection Name
        title = parser.get_doc_title()
        collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', title)

        # Create or get collections for text and tables
        text_collection = chroma_client.get_or_create_collection(name=collection_name)
        table_collection = chroma_client.get_or_create_collection(name=f"{collection_name}_tables")

        # Check to see what the max page that has already been processed and stored in the collection
        existing_ids = []

        if text_collection.count() > 0:
            print(f"Existing IDs in text collection '{collection_name}': {text_collection.get()['ids']}")
            existing_ids += text_collection.get()['ids']
        if table_collection.count() > 0:
            existing_ids += table_collection.get()['ids']

        existing_page_numbers = [int(doc_id.split("_")[1]) for doc_id in existing_ids if doc_id.startswith("page_")]
        if existing_page_numbers:
            max_existing_page = max(existing_page_numbers)
            logger.info(f"Max existing page in collection: {max_existing_page}")
            if args.start_page != -1 and args.start_page <= max_existing_page:
                logger.warning(f"Start page {args.start_page} is less than or equal to the max existing page {max_existing_page}.")
                logger.info("This may result in duplicate entries in the collection. Exiting...")
                exit(1)
            elif args.start_page == -1:
                args.start_page = max_existing_page + 1
                logger.info(f"Setting start page to {args.start_page} to avoid duplicates.")

        if args.start_page == -1:
            args.start_page = 0  # Default to the first page if not specified

        logger.info(f"Processing PDF ({title}): {args.path}")
        parser.parse(
            text_collection=text_collection,
            table_collection=table_collection,
            start_page=args.start_page,
            pages_to_parse=args.pages
        )
    else:
        logger.error(f"File {args.path} does not exist.")


# import os
# import sys

# import logging
# from dotenv import load_dotenv

# from typing import TypedDict
# # from langchain_openai import ChatOpenAI
# from langchain_openai import AzureChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate
# # from langchain_core.pydantic_v1 import BaseModel, Field
# from pydantic import BaseModel, Field
# from langchain_chroma import Chroma
# from langchain_openai import OpenAIEmbeddings
# from langgraph.graph import StateGraph, END

# logger = logging.getLogger(__name__)

# # 1. Define the desired JSON structure
# class DocumentSchema(BaseModel):
#     title: str = Field(description="The title of the document")
#     summary: str = Field(description="A brief summary of the text")
#     entities: list[str] = Field(description="Key entities mentioned in the text")
#     category: str = Field(description="The topic category")

# # 2. Define the Graph State
# class GraphState(TypedDict):
#     raw_text: str
#     structured_data: dict
#     db_path: str

# # 3. Initialize LLM with structured output
# load_dotenv()

# required_vars = ["OPENAI_ENDPOINT", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_API_VERSION"]
# missing_vars = [var for var in required_vars if not os.getenv(var)]
# if missing_vars:
#     logger.error(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
#     logger.error("Please check your .env file.")
#     sys.exit(1)

# # llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
# llm = AzureChatOpenAI(
#     azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
#     api_key=os.getenv("OPENAI_API_KEY"),
#     azure_deployment=os.getenv("OPENAI_MODEL"),
#     api_version=os.getenv("OPENAI_API_VERSION"),
#     temperature=0.7
# )
# structured_llm = llm.with_structured_output(DocumentSchema)

# # Node 1: Extract JSON from Text
# def extractor_node(state: GraphState):
#     prompt = ChatPromptTemplate.from_template("Extract information from this text: {text}")
#     chain = prompt | structured_llm
#     result = chain.invoke({"text": state["raw_text"]})
#     return {"structured_data": result.dict()}

# # Node 2: Store in ChromaDB
# def storage_node(state: GraphState):
#     db = Chroma(
#         persist_directory=state["db_path"],
#         embedding_function=OpenAIEmbeddings()
#     )
#     # Convert dict to string for storage
#     content = str(state["structured_data"])
#     db.add_texts(texts=[content], metadatas=[state["structured_data"]])
#     return {"structured_data": state["structured_data"]}

# # 4. Build the Graph
# workflow = StateGraph(GraphState)

# workflow.add_node("extract", extractor_node)
# workflow.add_node("store", storage_node)

# workflow.set_entry_point("extract")
# workflow.add_edge("extract", "store")
# workflow.add_edge("store", END)

# app = workflow.compile()

# # 5. Usage
# input_text = "LangGraph is a library for building stateful, multi-actor applications with LLMs."
# config = {"raw_text": input_text, "db_path": "./chroma_db"}

# result = app.invoke(config)
# print("Stored JSON:", result["structured_data"])