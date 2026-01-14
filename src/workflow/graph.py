from langgraph.graph import StateGraph, START, END
from langfuse.langchain import CallbackHandler
from src.workflow.state import InvoiceState
from src.workflow.nodes import surveyor, worker, mapper, auditor, detective, critic, mathematics, supplier_extractor
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
    workflow.add_node("supplier_extractor", supplier_extractor.extract_supplier_details)
    
    # Define Edges
    workflow.add_edge(START, "surveyor")
    workflow.add_edge("surveyor", "worker")
    
    # Parallel Supplier Extraction (Start from Surveyor or Start? Start is fine, but Surveyor gives us image path reliably)
    # Let's run it parallel to Worker. Surveyor -> Supplier Extractor
    workflow.add_edge("surveyor", "supplier_extractor")
    workflow.add_edge("supplier_extractor", END) # It's a sidequest, effectively.
    
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
        elif verdict == "RETRY_OCR" and state.get("retry_count", 0) < 3:
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

async def run_extraction_pipeline(image_path: str, user_email: str, public_url: str = None):
    """
    Entry point to run the new graph-based pipeline.
    Initializes state and invokes the graph.
    """
    logger.info(f"Starting Extraction Graph for {image_path} (User: {user_email})")
    
    # APP is already compiled globally
    
    initial_state = {
        "image_path": image_path,
        "public_url": public_url,  # Inject public URL
        "user_email": user_email,
        "extraction_plan": [],
        "line_item_fragments": [],
        "global_modifiers": {},
        "final_output": {},
        "error_logs": []
    }
    
    # Initialize Langfuse Callback
    try:
        langfuse_handler = CallbackHandler()
        callbacks = [langfuse_handler]
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse Callback: {e}")
        callbacks = []
    
    # Invoke Graph
    result_state = await APP.ainvoke(initial_state, config={"callbacks": callbacks})
    
    # Extract final output
    final_output = result_state.get("final_output")
    
    # Fallback: If pipeline ended without explicit Final Output (e.g. Retry Exhausted), construct it now
    if not final_output:
        logger.warning("Pipeline ended without Final Output. Constructing from State (Best Effort).")
        headers = result_state.get("global_modifiers", {})
        lines = result_state.get("line_items") or result_state.get("line_item_fragments", [])
        
        final_output = headers.copy()
        final_output["Line_Items"] = lines
        
    # MERGE Raw Text for Vector Storage (RAG)
    raw_rows = result_state.get("raw_text_rows", [])
    if raw_rows:
        # Deduplicate/Join (Worker might produce duplicates if retried, but add operator handles it)
        # Just simple join is enough for embeddings
        final_output["raw_text"] = "\n".join(raw_rows)
        
    # MERGE Supplier Details into Final Output
    supplier_details = result_state.get("supplier_details")
    if supplier_details:
        logger.info(f"Merging Supplier Details into Output: {supplier_details}")
        final_output["supplier_details"] = supplier_details
        
    error_logs = result_state.get("error_logs", [])
    
    if error_logs:
        logger.warning(f"Pipeline completed with errors: {error_logs}")
        
    return final_output
