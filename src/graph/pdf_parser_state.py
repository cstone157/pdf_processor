from typing import TypedDict
from pdfplumber import PDF

# Define the structure of our state
class GraphState(TypedDict):
  """
  Represents the state of our graph.
  Attributes:
    reader: The PDF reader object.
    pages_read: The number of pages that have been read.
  """
  reader: PDF
  pages_read: int
  table_of_contents: dict
  