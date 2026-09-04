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


def _read_sections_(sections, pages, page_offset = 0, next_section=None, to_end=False) -> list:
    """
    Reads in a section of the PDF document.
    Returns:
        list: A list of sections read from the PDF.
    """
    statement = _agents_statements_["pdf_sections"]
    messages = [
        SystemMessage(content=statement),
        HumanMessage(content="")
    ]


    prev_page = sections[0]["page_ref"]
    logger.info(f"Reading initial section {sections[0]['section']} from page unoffset {prev_page} vs offset {prev_page + page_offset}")
    page = pages[prev_page + page_offset]
    text = page.extract_text() + "\n"

    # Loop throught the sections and read in the text from the pages, if we 
    # encounter a new page then we need to read in all of the pages in between.
    for section in sections[1:]:
        if prev_page != section["page_ref"]:
            while prev_page < section["page_ref"]:
                prev_page += 1
                logger.info(f"Reading section {section['section']} from page unoffset {prev_page} vs offset {prev_page + page_offset}")
                page = pages[prev_page + page_offset]
                text += page.extract_text() + "\n"

    # Check and see if there is a next section, if so then we need to read 
    # in all of the pages until we reach the next section.
    if next_section is not None:
        while prev_page + 1 < next_section["page_ref"]:
            prev_page += 1
            logger.info(f"Reading next_section {next_section['section']} from page unoffset {prev_page} vs offset {prev_page + page_offset}")
            page = pages[prev_page + page_offset]
            text += page.extract_text() + "\n"
    # Check and see if we need to read until the end of the document, if so then we need to read
    # in all of the pages until we reach the end of the document.
    elif to_end:
        while prev_page + page_offset < len(pages) - 1:
            prev_page += 1
            logger.info(f"Reading trailing sections from page unoffset {prev_page} vs offset {prev_page + page_offset}")
            page = pages[prev_page + page_offset]
            text += page.extract_text() + "\n"

    # messages[1] = HumanMessage(content=page.extract_text())
    messages[1] = HumanMessage(content=text)
    response = _llm_.invoke(messages)

    # Store our results in the state, and reset our bulk_sections
    logger.info(f"Section results: {response.content[:100]}...")
    content = response.content
    if content.startswith("```json"):
        content = json.loads(content[8:-3])
    else:
        content = json.loads(content)

    return content


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
    
    # Check and see if tables of contents haven't been parsed, or if the maximum number of
    # pages read exceed the area covered under the current table_of_contents covered.
    # Also, check if the tables of contents is empty, if so then let's start there
    if not state["table_of_contents"]["scanned"]:
        return "read_table_of_contents"

    if state["scanned_sections"] < state["max_sections"]:
        return "read_section"
    if state["scanned_tables"] < state["max_tables"]:
        return "read_table"

    return "summary_section"


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
    if "table_of_contents" not in state:
        state["table_of_contents"] = {
            "scanned": False,
            "table_of_contents_offset": 0,
            "sections": [],
            "tables": [],
            "figures": []
        }

    if "sections" not in state:
        state["sections"] = {}
        state["max_sections"] = 0
        state["scanned_sections"] = 0
    if "tables" not in state:
        state["tables"] = {}
        state["max_tables"] = 0
        state["scanned_tables"] = 0
    return state



def read_table_of_contents(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Table of Contents =============================")

    # Start at the most recent page, loop through pages until we run out of table of contents
    current_page = 0
    statement = _agents_statements_["pdf_table_of_contents"]

    # If we encounter a tables of contents, flip our status to True.
    toc_first = False
    toc_encountered = False

    # What is the maximum page covered under the table of contents
    tables_of_contents_max_page = 0

    messages = [
        SystemMessage(content=statement),
        HumanMessage(content="")
    ]

    logger.info(f"Agent beginning looking for all of the table_of_contents pages in our document.")
    logger.info(f"Maximum number of pages {len(state['pages'])}.")

    while True:
        if current_page >= len(state["pages"]):
            logger.info("Exiting table of contents parser.  Reached the end of the document.")
            break

        logger.info(f"Submitting page {current_page} to be scanned.")
        page = state["pages"][current_page]
        messages[1] = HumanMessage(content=page.extract_text())
        response = _llm_.invoke(messages)
        toc_update = response.content
        if toc_update.strip().lower() == 'none' or toc_update is None:
            # If the LLM hasn't detected a table of contensts, but we used to dealing with 
            # a table of contents, we'll go ahead and jump to the end of the section that we
            # we discovered in our table of contents, and begin rescanning.
            if toc_encountered:
                if not toc_first:
                    toc_first = True
                    state["table_of_contents"]["table_of_contents_offset"] = current_page - 1 # Store the offset of the table of contents, so we can adjust our page numbers later on.
                    logger.info(f" ============================= Estimated offset of page numbers: {current_page} =============================")

                toc_encountered = False
                current_page = tables_of_contents_max_page
        else:
            logger.info(f"Page {current_page} content '{page.extract_text()[:20]}...'")
            toc_encountered = True
            if toc_update.startswith("```json"):
                # logger.info(f"Stripping ```json")
                toc_update = json.loads(toc_update[8:-3])
            else:
                # logger.info(f"Don't strip ```json")
                toc_update = json.loads(toc_update)

            # Loop through the TOC and update the appropriate portions of the table_of_contents
            for item in toc_update["meta_data"]["items"]:
                # Covert the page_refs to an int
                item['page_ref'] = int(item['page_ref'])

                # IF the TOC was encountered then calculate the number of pages to be gone through
                if tables_of_contents_max_page < item["page_ref"]:
                    tables_of_contents_max_page = item["page_ref"]

                if item["section"].lower().strip().startswith("table"):
                    state["table_of_contents"]["tables"].append(item)
                elif item["section"].lower().strip().startswith("figure"):
                    state["table_of_contents"]["figures"].append(item)
                else:
                    state["table_of_contents"]["sections"].append(item)

        # Increment the current page
        current_page += 1

    state["table_of_contents"]["scanned"] = True
    state["max_sections"] = len(state["table_of_contents"]["sections"])
    state["max_tables"] = len(state["table_of_contents"]["tables"])

    logger.info(f" ============================= End of Read Table of Contents =============================")
    return state


def read_table(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Table =============================")
    state["scanned_tables"] = state["max_tables"]
    return state


def read_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Sections Section =============================")
    bulk_sections = []
    currnet_section = None

    page_offset = state["table_of_contents"]["table_of_contents_offset"]

    while state["scanned_sections"] < state["max_sections"]:
        # Pull up the next section
        currnet_section = state["table_of_contents"]["sections"][state["scanned_sections"]]

        # If the bulk_sections, is empty go ahead and append it to the previous bulk section
        if len(bulk_sections) == 0:
            bulk_sections.append(currnet_section)
        # Go through the other sections and try and see if the new section should be added,
        # if no then go ahead and submit the previous bulk section for transcription.
        else:
            pl = bulk_sections[0]["section"].split(".")[0]
            cl = currnet_section["section"].split(".")[0]

            # HACK: Initial draft, just check if were in a whole new top-lvl section
            if pl != cl:
                # Store our results in the state, and reset our bulk_sections
                section = _read_sections_(bulk_sections, state["pages"], page_offset, next_section=currnet_section)
                state["sections"][pl] = section
                bulk_sections = []
                logger.info(f"Section ({pl}) results: {section[:100]}...")
            else:
                bulk_sections.append(currnet_section)

        # Increment by one and roll over to the next section
        state["scanned_sections"] += 1

    if len(bulk_sections) > 0:
        # Store our results in the state, and reset our bulk_sections
        pl = bulk_sections[0]["section"].split(".")[0]
        section = _read_sections_(bulk_sections, state["pages"], page_offset, to_end=True)
        state["sections"][pl] = section
        logger.info(f"Final Section ({pl}) results: {section[:100]}...")


    # HACK: ensure we exit out of our function
    # state["scanned_sections"] = state["max_sections"]
    logger.info(f" ============================= End of Read Sections Section =============================")
    return state


def read_figure(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Read Figure =============================")
    return state


def summary_section(state: PdfParseState) -> PdfParseState:
    """
    Args:
        state (PdfParseState): The current graph state.
    Returns:
        PdfParseState: The updated graph state.
    """
    logger.info(f" ============================= Summary Section =============================")
    # Determine output path
    state_export_path = state.get("state_export_path")

    if state_export_path:
        state_export_path = Path(state_export_path).with_suffix(".json")
        logger.info(f"Saving state to JSON at: {state_export_path}")
    else:
        # Fallback: save next to working directory with a generic name
        # output_path = Path("state_summary.json")
        state_export_path = input("Please provide a file path to save the state summary (e.g., 'state_summary.json'), or skip: ").strip()
        state_export_path = None if not state_export_path or state_export_path.lower() == "skip" else Path(state_export_path)

    if state_export_path:
        try:
            with open(state_export_path, "w", encoding="utf-8") as f:
                object_to_serialize = {k: v for k, v in state.items() if k != "pages"}  # Exclude 'pages' from serialization
                json.dump(object_to_serialize, f, ensure_ascii=False, indent=2)
            logger.info("State successfully written to JSON.")
        except Exception as e:
            logger.error(f"Failed to write state JSON to {state_export_path}: {e}")
    else:
        logger.info("No output path provided. State summary not saved.")

    return state

