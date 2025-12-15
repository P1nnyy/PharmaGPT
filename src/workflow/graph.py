from langgraph.graph import StateGraph, START, END
from src.workflow.state import InvoiceState
from src.workflow.nodes import surveyor, worker, mapper, auditor, detective, critic, mathematics
from src.utils.logging_config import get_logger

# Setup Logging
logger = get_logger(__name__)

def build_graph():
    """
    Constructs the Invoice Extraction Graph.
    Flow: START -> Surveyor -> Worker -> Mapper -> Auditor -> Detective -> END
    """
    workflow = StateGraph(InvoiceState)
    
    # Add Nodes
    workflow.add_node("surveyor", surveyor.survey_document)
    workflow.add_node("worker", worker.execute_extraction)
    workflow.add_node("mapper", mapper.execute_mapping)
    workflow.add_node("auditor", auditor.audit_extraction)
    workflow.add_node("detective", detective.detective_work)
    workflow.add_node("critic", critic.critique_extraction)
    workflow.add_node("solver", mathematics.apply_correction)
    
    # Define Edges
    workflow.add_edge(START, "surveyor")
    workflow.add_edge("surveyor", "worker")
    workflow.add_edge("worker", "mapper")
    workflow.add_edge("mapper", "auditor")
    workflow.add_edge("auditor", "detective")
    workflow.add_edge("detective", "critic")
    
    # Conditional Feedback Loop
    def route_critic(state):
        verdict = state.get("critic_verdict")
        logger.info(f"Graph Decision: Verdict is {verdict}")
        
        if verdict in ["APPLY_MARKUP", "APPLY_MARKDOWN"]:
            return "solver"
        elif verdict == "RETRY_OCR" and state.get("retry_count", 0) < 2:
            return "worker"
        return "end"

    workflow.add_conditional_edges(
        "critic",
        route_critic,
        {
            "solver": "solver",
            "worker": "worker",
            "end": END
        }
    )
    
    workflow.add_edge("solver", END)
    
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
    final_output = result_state.get("final_output")
    
    # Fallback: If pipeline ended without explicit Final Output (e.g. Retry Exhausted), construct it now
    if not final_output:
        logger.warning("Pipeline ended without Final Output. Constructing from State (Best Effort).")
        headers = result_state.get("global_modifiers", {})
        lines = result_state.get("line_items") or result_state.get("line_item_fragments", [])
        
        final_output = headers.copy()
        final_output["Line_Items"] = lines
        
    error_logs = result_state.get("error_logs", [])
    
    if error_logs:
        logger.warning(f"Pipeline completed with errors: {error_logs}")
        
    return final_output
