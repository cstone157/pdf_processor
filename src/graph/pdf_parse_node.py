import logging
from pdfplumber import PDF

from typing import Literal

from graph.pdf_parse_state import PdfParseState

logger = logging.getLogger(__name__)
_llm_ = None                                         # Reference to a global LLM object, initialized later in the workflow
_reader_ = None                                      # Reference to a global PDF reader object, initialized later in the workflow


def _initialze_(llm, reader):
    """
    Initializes the global LLM object.
    Args:
        llm: The LLM object to be used in the workflow.
    """
    global _llm_
    global _reader_

    _llm_ = llm
    _reader_ = reader


def initial_node(state: PdfParseState) -> PdfParseState:
    """
    The initial node in the graph state.  Checks to see if the enviroment
    has been correctly initialized.
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info("Starting initial node processing...")

    if _llm_ is None or _reader_ is None:
        raise Exception("pdf_parser improperly initialized.  Exiting.")

    return state


def initial_routing_logic(state: PdfParseState) -> Literal["chunking_agent", "error_agent"]:
    """
    Determines the next agent to invoke based on the current state.
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        str: The name of the next agent to invoke.
    """
    logger.info("Routing to the appropriate agent...")
    
    # Placeholder logic for routing
    if "chunked_text" not in state.keys() or len(state.chunked_text) == 0:
        return "chunking_agent"
    else:
        return "error_agent"


def chunking_agent(state: PdfParseState) -> PdfParseState:
    """
    Processes the PDF in chunks and updates the graph state.
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info("Processing PDF in chunks...")

    return state


def error_agent(state: PdfParseState) -> PdfParseState:
    """
    Handles errors in the graph state.
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.error("An error occurred while processing the PDF.")
    return state