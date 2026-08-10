import re
import logging
import pdfplumber
import nltk
from nltk.corpus import stopwords, words
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist

logger = logging.getLogger(__name__)

class DocPdfParser:
    COVER_PAGE = "cover_page"
    TABLE_OF_CONTENTS = "table_of_contents"
    FOREWORD = "foreword"
    DISTRIBUTION_WARNING = "distribution_warning"
    INTENTIONALLY_LEFT_BLANK = "intentionally_left_blank"
    REGULAR_PAGE = "regular_page"


    PATTERNS = {
        "cover_page": [ r"INCH-POUND" ],
        "table_of_contents": [ r"TABLE OF CONTENT", r"SECTION \d+\nTABLE OF CONTENTS" ],
        "foreword": [ r"FOREWORD" ],
        "distribution_warning": [ r"DISTRIBUTION WARNING" ],
        "intentionally_left_blank": [ r"THIS PAGE INTENTIONALLY LEFT BLANK" ]
    }

    # BLOCK_PATTERN = r"(\d\.[\d\.]* [^\W_-]+[^\s]*)"
    # BLOCK_PATTERN = r"^(\d+(?:\.\d+)*)\s+(.*)"
    BLOCK_PATTERN = r"(?m)^(?=\d+(\.\d+)+)"
    BLOCK_PATTERN2 = r"^\d\.[\d\.]*"

    def __init__(self, file_path):
        """
        Initializes the DocPdfParser with the specified PDF file path.
        Args:
            file_path (str): Path to the PDF file to be parsed.
        """
        self.reader = pdfplumber.open(file_path)
        self.__doc_title__ = None

    def get_doc_title(self):
        """
        Retrieves the title from the 2nd line of the first page.
        """
        if self.__doc_title__ is None:
            page1_text = self.reader.pages[0].extract_text()
            lines = page1_text.splitlines()
            # Return the 2nd line (index 1), stripped of whitespace
            self.__doc_title__ = lines[1].strip() if len(lines) > 1 else "default_collection"
        return self.__doc_title__

    def pre_process_text(self, text):
        """
        Pre-processes the extracted text by tokenizing, removing stopwords, and calculating word frequency.
        Args:
            text (str): The extracted text from the PDF page.
        Returns:
            str: The pre-processed text.
        """
        # Check to see if the document name is available and strip it from the beginning of the text to avoid redundancy
        document_name = self.get_doc_title()
        if document_name and text.upper().strip().startswith(document_name):
            text = text[len(document_name):].strip()

        doc_section = text[text.rfind('\n'):].strip().split('-')
        if len(doc_section) > 1:
            section_page_num = doc_section[1]
            doc_section = doc_section[0]
        else:
            section_page_num = None
            doc_section = None

        # text = text[:text.rfind('\n')].strip().replace("\n", " ")
        text = text[:text.rfind('\n')].strip()
        return (text, doc_section, section_page_num)

    def get_page_type(self, text, prev_page_type=None):
        """
        Determines the type of the page based on its text content.
        Args:
            text (str): The extracted text from the page.
        Returns:
            str: The type of the page (e.g., cover_page, table_of_contents, etc.).
        """
        # Check if this page is a continuation of the table of contents
        cln_text = text.upper().strip()
        # if prev_page_type == self.TABLE_OF_CONTENTS and cln_text.startswith("TABLE"):
        #     return self.TABLE_OF_CONTENTS

        for page_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, cln_text):
                    return getattr(self, page_type.upper())
        return self.REGULAR_PAGE


    def parse(self, text_collection=None, table_collection=None, start_page=0, pages_to_parse=100):
        """
        Parses the PDF document and extracts text from each page.
        Args:
            text_collection (chromadb.Collection): Collection for storing text content.
            table_collection (chromadb.Collection): Collection for storing table data.
            start_page (int): Start page number (0-indexed).
            pages_to_parse (int): Number of pages to parse.
        """
        # Blocks of text to be stored
        blocks = []
        mrg_blk = ""

        for page_number in range(start_page, min(start_page + pages_to_parse, len(self.reader.pages))):
            page = self.reader.pages[page_number]
            text = page.extract_text()
            (pre_processed_text, doc_section, section_page_num)  = self.pre_process_text(text)
            page_type = self.get_page_type(pre_processed_text)

            # Store the text in the appropriate collection based on the page type
            if page_type == self.REGULAR_PAGE and text_collection is not None:
                blocks += self.split_text_into_blocks(pre_processed_text)
                logger.info(f"Page {page_number} is of type {page_type}.  Pre-processed text: {pre_processed_text[:20]}...")  # Print first 20 characters of the text
                logger.info(f"\n\n{pre_processed_text}\n\n")
                logger.info(f"Blocks extracted from page {page_number}: {blocks}")

                for block in blocks:
                    logger.info(f"BLOCK ===> {block[:50]}... <===")
                    if block.strip():
                        pass
                    if re.search(self.BLOCK_PATTERN2, block):
                        if mrg_blk.strip():
                            self.store_text_in_collection(mrg_blk, text_collection, page_number, self.get_doc_title())
                        mrg_blk = block
                    else:
                        mrg_blk += " " + block

                blocks = blocks[-1:]
                # self.store_text_in_collection(pre_processed_text, text_collection, page_number, self.get_doc_title())
                logger.info(f"Page {page_number} processed. ===================================<")
            ## TO-DO: add a check to see if this is a table and parse/store it
            # elif page_type == self.TABLE and table_collection is not None:
            #     self.store_text_in_collection(pre_processed_text, table_collection, page_number, self.get_doc_title())
            else:
                logger.info(f"Skipping {page_number} becuase the page was {page_type}")

        logger.info(f"Last block not submitted {mrg_blk}")

    def split_text_into_blocks(self, text, prev_blocks=None):
        """
        Split the text into blocks, and removed the unnecissary new-lines
        Args:
            text (str): The text to split into blocks
        """
        #     Pattern r'(?m)^(?=\d+(\.\d+)+)', results is a wierd split, where the last number of the 
        # list is being duplicated, repeatedly.  Go ahead and remove any element that is less than 3 characters,
        # or are empty
        result = [s.strip() for s in re.split(self.BLOCK_PATTERN, text, re.MULTILINE) if s.strip() and len(s.strip()) >= 3]
        # Remove the \n and replace with space
        result = [s.replace("\n", " ") for s in result]
        return result

    def store_text_in_collection(self, text, collection, page_number, document_name=None):
        """
        Stores the extracted text in the specified ChromaDB collection.
        Args:
            text (str): The extracted text.
            collection (chromadb.Collection): The ChromaDB collection to store the text.
            page_number (int): The current page number.
        """
        words = [w.lower() for w in word_tokenize(text) if w.isalnum()]
        keywords = [word[0] for word in FreqDist([w for w in words if w not in set(stopwords.words('english'))]).most_common(10)]

        if collection is not None:
            doc_id = f"page_{page_number}"
            metadata = {"page_number": page_number, "keywords": ", ".join(keywords)}
            collection.add(documents=[text], ids=[doc_id], metadatas=[metadata])

            logger.info(f"Stored text for page {page_number} in collection '{collection.name}' with ID '{doc_id}' and metadata: {metadata}.  Value stored:\n{text[:100]}\n")  # Print first 100 characters of the text
