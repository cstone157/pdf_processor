import logging
from pathlib import Path
from pdfplumber import PDF

from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage

from graph.pdf_parse_state import PdfParseState

logger = logging.getLogger(__name__)
_llm_ = None                                         # Reference to a global LLM object, initialized later in the workflow
_reader_ = None                                      # Reference to a global PDF reader object, initialized later in the workflow

_agents_statements_ = None


def _initialze_(llm, reader, statement_folder_path="./agents"):
    """
    Initializes the global LLM object.
    Args:
        llm: The LLM object to be used in the workflow.
    """
    global _llm_, _reader_, _agents_statements_

    _llm_ = llm
    _reader_ = reader
    _agents_statements_ = {}

    # read in all of the agent_statements, and name them after the different folders
    statement_folder_path = Path(statement_folder_path)
    for file_path in statement_folder_path.rglob("*"):
        if file_path.is_file():
            logger.info(f"Reading {file_path}")
            key = file_path.parent.name

            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    _agents_statements_[key] = content
                    logger.info(f"Inserted  {file_path}")
            except Exception as e:
                logger.error(f"Error while trying to ready in {file_path}")
                logger.error(f"Stack trace is: \n {e}")


# ---------------------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------------------
def routing_logic(state: PdfParseState) -> Literal["read_table_of_contents", "read_table", "read_section", "summary_section"]:
    """
    Determines the next agent to invoke based on the current state.
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        str: The name of the next agent to invoke.
    """
    logger.info("Routing to the appropriate agent...")
    
    # Check and see if the pages_read is past the end of the document, if so exit
    if state["pages_read"] >= len(state["pages"]):
        return "summary_section"

    # Check and see if tables of contents haven't been parsed, or if the maximum number of
    # pages read exceed the area covered under the current table_of_contents covered.
    # Also, check if the tables of contents is empty, if so then let's start there
    if state["pages_read"] < state["tables_of_contents_max_page"] or not state["table_of_contents"]:
        return "read_table_of_contents"

    return "read_section"


# ---------------------------------------------------------------------------------------
# The individual nodes that compose our graph
# ---------------------------------------------------------------------------------------
def read_initial_document(state: PdfParseState) -> PdfParseState:
    """
    The node that reads in a single document, it should use the document next should be 
    read in.

    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info("Setting up to read the document ...")

    if "pages" not in state:
        state["pages"] = _reader_.pages
    if "pages_read" not in state:
        state["pages_read"] = 0
    if "table_of_contents" not in state:
        state["table_of_contents"] = {}
    if "tables_of_contents_max_page" not in state:
        state["tables_of_contents_max_page"] = 0
    if "sections" not in state:
        state["sections"] = {}
    if "tables" not in state:
        state["tables"] = {}
    if "appendix" not in state:
        state["appendix"] = {}
    return state

def read_document(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    return state


def read_table_of_contents(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info("Starting reading the tables of contents ...")

    # Start at the most recent page, loop through pages until we run out of table of contents
    pages_read = 0
    current_page = state["pages_read"]
    statement = _agents_statements_["pdf_table_of_contents"]

    # If we encounter a tables of contents, flip our status to True.
    toc_encounted = False

    messages = [
        SystemMessage(content=statement),
        HumanMessage(content="")
    ]

    while True:
        if pages_read >= 50:
            break
        if current_page > len(state["pages"]):
            logger.info("Exiting table of contents parser.  Reached the end of the document.")
            break

        page = state["pages"][current_page]
        logger.info(f"Page {current_page} content '{page.extract_text()[:30]}...'")
        messages[1] = HumanMessage(content=page.extract_text())
        response = _llm_.invoke(messages)

        if response is not None:
            pages_read += 1
            current_page += 1
        elif response is None and not toc_encounted:
            toc_encounted = True
            pages_read += 1
            current_page += 1
        elif response is None and toc_encounted:
            break


        print(response.content)


    state["pages_read"] += pages_read
    # HACK: Forces an exit from the function
    state["tables_of_contents_max_page"] = len(state["pages"])
    return state


def read_table(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    state["pages_read"] += 1
    return state


def read_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    state["pages_read"] += 1
    return state


def summary_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    state["pages_read"] += 1
    return state

