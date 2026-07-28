import os
import re
import uuid
import argparse
import chromadb
from pypdf import PdfReader
from tqdm import tqdm
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

chroma_client = chromadb.PersistentClient(path="./chroma_db")

def get_doc_title(reader):
    """
    Retrieves the title from the 2nd line of the first page.
    """
    page1_text = reader.pages[0].extract_text()
    lines = page1_text.splitlines()
    # Return the 2nd line (index 1), stripped of whitespace
    return lines[1].strip() if len(lines) > 1 else "default_collection"

def parse_table(text, page):
    """
    Parses the table of contents text to extract headers.
    """
    if text.strip().startswith("TABLE"):
        print("========================================================")
        print(text)
        print("========================================================")

        table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
            "join_y_tolerance": 5,      # Helps merge text vertically split across lines
            "join_x_tolerance": 2,
            "explicit_vertical_lines": [],
            "explicit_horizontal_lines": [],
            "snap_y_tolerance": 3,
        }
        tables = page.extract_tables(table_settings=table_settings)
        
        print(tables)
        print("========================================================")
        return tables if tables else None
    return None

def get_last_processed_header(collection):
    """
    Retrieves the last processed header from the collection's metadata.
    """
    results = collection.get(include=['metadatas'])
    if not results or not results['metadatas']:
        return None
    headers = [m.get('header') for m in results['metadatas'] if 'header' in m]
    return headers[-1] if headers else None

def check_intentionally_blank(text):
    """
    Checks if the page text indicates that it is intentionally left blank.
    """
    return "THIS PAGE INTENTIONALLY LEFT BLANK" in text.strip().upper()

def check_table_of_contents(text):
    """
    Checks if the page text indicates that it is a Table of Contents.
    """
    return "TABLE OF CONTENTS" in text.strip().upper()

def check_page_to_skip(text):
    """
    Checks if the page should be skipped.
    """
    if not text:
        return True
    if check_intentionally_blank(text):
        return True
    if check_table_of_contents(text):
        return True
    return False

def process_and_store(reader, max_pages, collection, doc_title, source_file=None):
    """
    Processes the PDF, extracts text, splits into blocks, and stores them in the collection.
    """
    full_text = ""
    num_pages = min(len(reader.pages), max_pages)
    
    # 1. Extract text and strip the doc_title from the start of every page
    print("Extracting text and cleaning pages...")
    for i in range(num_pages):
        text = reader.pages[i].extract_text()
        if check_page_to_skip(text):
            # Skip pages with no relevant content
            continue  

        if i == 542 or i == 543 or i == 544:
            print(f"Page {i+1} text: {text}")
            print("========================================================")

        # Find the pages that are tables and parse the table and store into a different collection
        tbl = parse_table(text, reader.pages[i])
        if tbl is not None:
            continue  

        # Remove the document title from the start of the text if it exists
        text = text[len(doc_title):].lstrip()
        full_text += text + "\n"




    # words = [w.lower() for w in word_tokenize(content) if w.isalnum()]
    # keywords = [word[0] for word in FreqDist([w for w in words if w not in set(stopwords.words('english'))]).most_common(10)]
    
    # collection.add(
    #     documents=[content],
    #     metadatas={"source": os.path.basename(source_file) if source_file else os.path.basename(args.path), "header": header, "keywords": ", ".join(keywords)},
    #     ids=[str(uuid.uuid4())]
    # )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF by block headers (e.g., 3.6.14).")
    parser.add_argument("path", help="Path to the PDF file")
    parser.add_argument("-n", "--pages", type=int, default=100, help="Number of pages")
    args = parser.parse_args()

    if os.path.exists(args.path):
        reader = PdfReader(args.path)

        # Determine Title and Collection Name
        title = get_doc_title(reader)
        col_name = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
        collection = chroma_client.get_or_create_collection(name=col_name)
        
        print(f"Document Title: {title}")
        print(f"Using Collection: {col_name}")
        
        process_and_store(reader, args.pages, collection, title, source_file=args.path)
        print(f"Done. Total blocks: {collection.count()}")
    else:
        print("File not found.")