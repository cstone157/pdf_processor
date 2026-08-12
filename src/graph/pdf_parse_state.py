from typing import TypedDict
from pdfplumber import PDF

# Define the structure of our state
class PdfParseState(TypedDict):
  """
  Represents the state of our graph.
  Attributes:
    reader: The PDF reader object.
    pages_read: The number of pages that have been read.
  """
  pages_read: int
  text: str
  sections: list
  tables: list
  appendix: list
  table_of_contents: dict
  