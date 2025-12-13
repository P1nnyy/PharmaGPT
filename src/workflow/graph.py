from langgraph.graph import StateGraph, START, END
from src.workflow.state import InvoiceState
from src.workflow.nodes import surveyor, worker, auditor
import logging

# Setup Logging
logger = logging.getLogger(__name__)

def build_graph():
    """
    Constructs the Invoice Extraction Graph.
    Flow: START -> Surveyor -> Worker -> Auditor -> END
    """
    workflow = StateGraph(InvoiceState)
    
    # Add Nodes
    workflow.add_node("surveyor", surveyor.survey_document)
    workflow.add_node("worker", worker.execute_extraction)
    workflow.add_node("auditor", auditor.audit_extraction)
    
    # Define Edges
    workflow.add_edge(START, "surveyor")
    workflow.add_edge("surveyor", "worker")
    workflow.add_edge("worker", "auditor")
    workflow.add_edge("auditor", END)
    
    return workflow.compile()

# Global Compilation (Compile once on startup)
APP = build_graph()

async def run_extraction_pipeline(image_path: str):
    """
    Entry point to run the new graph-based pipeline.
    Initializes state and invokes the graph.
    """
    logger.info(f"Starting Extraction Graph for {image_path}")
    
    # APP is already compiled globally
    
    initial_state = {
        "image_path": image_path,
        "extraction_plan": [],
        "line_item_fragments": [],
        "global_modifiers": {},
        "final_output": {},
        "error_logs": []
    }
    
    # Invoke Graph
    result_state = await APP.ainvoke(initial_state)
    
    # Extract final output
    final_output = result_state.get("final_output", {})
    error_logs = result_state.get("error_logs", [])
    
    if error_logs:
        logger.warning(f"Pipeline completed with errors: {error_logs}")
        
    return final_output
