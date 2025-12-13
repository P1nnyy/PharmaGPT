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

async def run_extraction_pipeline(image_path: str):
    """
    Entry point to run the new graph-based pipeline.
    Initializes state and invokes the graph.
    """
    logger.info(f"Starting Extraction Graph for {image_path}")
    
    app = build_graph()
    
    initial_state = {
        "image_path": image_path,
        "extraction_plan": [],
        "line_item_fragments": [],
        "global_modifiers": {},
        "final_output": {},
        "error_logs": []
    }
    
         
         # Simplest: Make this async and update callers. 
         # But the user asked for this function signature.
         
         # Let's try nest_asyncio logic or simply asyncio.run() assuming no running loop in test.
         # In FastAPI, uvicorn runs a loop. `asyncio.run` will FAIL.
         
         # Better fix: Make `run_extraction_pipeline` ASYNC.
         # Then update server.py to `await run_extraction_pipeline`.
         # Update test_math_diagnosis.py to `asyncio.run(run_extraction_pipeline)`.
         
         # Wait, I cannot easily change API signature without looking at all files.
         # Actually, Step 768 shows `analyze_invoice` is async.
         # `extracted_data = run_extraction_pipeline(tmp_path)` (It was called synchronously).
         
         # Strategy: Make `run_extraction_pipeline` ASYNC. Update Server and Test.
         
    
    # Correction: I will make run_extraction_pipeline async.
    # Invoke Graph
    result_state = await app.ainvoke(initial_state)
    
    # Extract final output
    final_output = result_state.get("final_output", {})
    error_logs = result_state.get("error_logs", [])
    
    if error_logs:
        logger.warning(f"Pipeline completed with errors: {error_logs}")
        
    return final_output
