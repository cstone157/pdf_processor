from typing import TypedDict
from pdfplumber import PDF

# Define the structure of our state
class PdfParseState(TypedDict):
  """
  Represents the state of our graph.
  Attributes:
    sections: the list of the resulting sections that have been read in
    tables: the list of the different tables that have been read in
    appendix: the list of the different appendix's that have been read in
    tables_of_contents: the dictionary of the table of contents
  """
  state_export_path: str
  pages: list
  table_of_contents: dict
  sections: list
  max_sections: int
  scanned_sections: int
  tables: list
  max_tables: int
  scanned_tables: int
  

  