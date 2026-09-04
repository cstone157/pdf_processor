import os
import re
import json
import logging

import pdfplumber

from langgraph.graph import StateGraph, START, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from utils import load_system_prompts, load_environment, load_arguments
from graph.pdf_parse_state import PdfParseState
import graph.pdf_parse_node


logger = logging.getLogger(__name__)
load_environment()                      # Load and validate environment variables
args = load_arguments()                 # Set up argument parser for command-line arguments


if __name__ == "__main__":
    # Set up logging based on command-line arguments
    if args.log:
        logging.basicConfig(filename=args.log_file, encoding='utf-8', level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s - %(levelname)s - %(message)s')

    if os.path.exists(args.path):
        # Initialize the PDF reader
        reader = pdfplumber.open(args.path)

        # Initialize the LLM with Azure OpenAI settings
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
            api_key=os.getenv("OPENAI_API_KEY"),
            azure_deployment=os.getenv("OPENAI_MODEL"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            temperature=0.7
        )
        graph.pdf_parse_node._initialze_(llm, reader)


        # Build graph
        body_nodes = [
            'read_initial_document', 'read_table_of_contents', 'read_table', 'read_section'#, 'read_figure'
        ]
        workflow = StateGraph(PdfParseState)           
        workflow.add_node('read_initial_document', graph.pdf_parse_node.read_initial_document)
        workflow.add_node('read_table_of_contents', graph.pdf_parse_node.read_table_of_contents)
        workflow.add_node('read_table', graph.pdf_parse_node.read_table)
        workflow.add_node('read_section', graph.pdf_parse_node.read_section)
        # workflow.add_node('read_figure', graph.pdf_parse_node.read_figure)
        workflow.add_node('summary_section', graph.pdf_parse_node.summary_section)

        # Define the flow
        workflow.add_edge(START, 'read_initial_document')
        for n in body_nodes:
            workflow.add_conditional_edges(n, 
                graph.pdf_parse_node.routing_logic,
                {
                    "read_table_of_contents": "read_table_of_contents",
                    "read_table": "read_table",
                    "read_section": "read_section",
                    # "read_figure": "read_figure",
                    "summary_section": "summary_section"
                }
            )
        
        workflow.add_edge('summary_section', END)

        # Compile and run the workflow
        app = workflow.compile()

        # Prepare initial state: either from JSON file (if provided and exists) or empty
        initial_state: PdfParseState
        if args.state and os.path.exists(args.state):
            try:
                with open(args.state, "r", encoding="utf-8") as f:
                    loaded_state = json.load(f)
                # Ensure the state_export_path matches the current state file path
                loaded_state["state_export_path"] = args.state
                initial_state = loaded_state  # type: ignore[assignment]
                logger.info(f"Loaded initial state from {args.state}")
            except Exception as e:
                logger.error(f"Failed to load state from {args.state}: {e}")
                initial_state = {}
        else:
            initial_state = {}

        # Print the ascii representation of the graph
        # print(app.get_graph().draw_ascii())  # Graph currently throwing an error (doesn't seem to like loops)

        # Run the graph and log the final output
        output = app.invoke(initial_state)
        print(f"=> Final output: ")
        for k in output.keys():
            if k != "pages": 
                print(f"-----> {k} : {json.dumps(output[k], indent=2)}")
    else:
        logger.error(f"File {args.path} does not exist.")
