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