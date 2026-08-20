import logging
import json
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
    logger.info(f" ============================= Routing Logic =============================")
    
    # Check and see if the pages_read is past the end of the document, if so exit
    if state["pages_read"] >= len(state["pages"]):
        return "summary_section"

    # Check and see if tables of contents haven't been parsed, or if the maximum number of
    # pages read exceed the area covered under the current table_of_contents covered.
    # Also, check if the tables of contents is empty, if so then let's start there
    if state["pages_read"] < state["tables_of_contents_max_page"] or state["tables_of_contents_max_page"] == -1:
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
    logger.info(f" ============================= Initial Read Document =============================")

    if "pages" not in state:
        state["pages"] = _reader_.pages
    if "pages_read" not in state:
        state["pages_read"] = 0
    if "table_of_contents" not in state:
        state["table_of_contents"] = {
            "sections": [],
            "tables": [],
            "figures": []
        }
    # Use the value of -1, to denote that our application hasn't started scanning for a table of contents yet
    # TO-DO: Check if we were passed a "table_of_contents", if so then set the state["tables_of_contents_max_page"]
    #        to the maximum value that has already been scanned by the document
    if "tables_of_contents_max_page" not in state:
        state["tables_of_contents_max_page"] = -1       
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
    logger.info(f" ============================= Read Document =============================")
    return state


def read_table_of_contents(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Table of Contents (page {state['pages_read']}) =============================")

    # Start at the most recent page, loop through pages until we run out of table of contents
    current_page = state["pages_read"]
    statement = _agents_statements_["pdf_table_of_contents"]

    # If we encounter a tables of contents, flip our status to True.
    toc_encounted = False

    messages = [
        SystemMessage(content=statement),
        HumanMessage(content="")
    ]

    while True:
        if current_page - state["pages_read"] >= 50:
            break
        if current_page > len(state["pages"]):
            logger.info("Exiting table of contents parser.  Reached the end of the document.")
            break

        page = state["pages"][current_page]
        messages[1] = HumanMessage(content=page.extract_text())
        response = _llm_.invoke(messages)
        toc_update = response.content
        if toc_update.strip().lower() == 'none':
            toc_update = None

        logger.info(f"Page {current_page} content '{page.extract_text()[:30]}...'")
        if toc_update:
            logger.info(f"  ==> Generated {toc_update[8:-3]}...")
        else:
            logger.info(f"  ==> NOTHING RETURNED, LLM DIDN'T DETECT TOC")

        # Check if our toc_update is None, then go ahead and finish up.
        if toc_update is None and toc_encounted:
            break
        # Otherwise, then go ahead and update our table_of_contents and store
        elif toc_update is not None:
            toc_encounted = True
            if toc_update.startswith("```json"):
                logger.info(f"Stripping ```json")
                toc_update = json.loads(toc_update[8:-3])
            else:
                logger.info(f"Don't strip ```json")
                toc_update = json.loads(toc_update)

            logger.info(f"{toc_update.keys()}")

            # Loop through the TOC and update the appropriate portions of the table_of_contents
            for item in toc_update["meta_data"]["items"]:
                # IF the TOC was encountered then calculate the number of pages to be gone through
                if state["tables_of_contents_max_page"] < item["page_ref"]:
                    state["tables_of_contents_max_page"] = item["page_ref"]

                if item["section"].lower().strip().startswith("table"):
                    state["table_of_contents"]["tables"].append(item)
                elif item["section"].lower().strip().startswith("figures"):
                    state["table_of_contents"]["tables"].append(item)
                else:
                    state["table_of_contents"]["sections"].append(item)
            
        # Increment the current page
        current_page += 1



    state["pages_read"] = current_page
    # HACK: Forces an exit from the function
    state["pages_read"] += len(state["pages"])
    logger.info(f" ============================= End of Read Table of Contents (page {state['pages_read']}) =============================")
    return state


def read_table(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Table (page {state['pages_read']}) =============================")
    state["pages_read"] += 1
    return state


def read_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Section (page {state['pages_read']}) =============================")
    state["pages_read"] += 1
    return state


def summary_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Summary Section =============================")
    return state

