from typing import Dict, Any, Callable
import asyncio
from langgraph.graph import StateGraph, START, END
from langfuse.langchain import CallbackHandler
from src.workflow.state import InvoiceState, SupplyChainState
from src.workflow.nodes import surveyor, worker, mapper, auditor, detective, critic, mathematics, supplier_extractor, researcher, inventory_agent, forecasting_agent
from src.utils.logging_config import get_logger

# Setup Logging
logger = get_logger(__name__)

def build_graph():
    """
    Constructs the Invoice Extraction Graph.
    Flow: START -> Surveyor -> Worker -> Mapper -> Auditor -> Detective -> Researcher -> Critic -> END
    """
    workflow = StateGraph(InvoiceState)
    
    # Add Nodes
    workflow.add_node("surveyor", surveyor.survey_document)
    workflow.add_node("worker", worker.execute_extraction)
    workflow.add_node("mapper", mapper.execute_mapping)
    workflow.add_node("auditor", auditor.audit_extraction)
    workflow.add_node("detective", detective.detective_work)
    workflow.add_node("researcher", researcher.enrich_line_items) # New Agent
    workflow.add_node("critic", critic.critique_extraction)
    workflow.add_node("solver", mathematics.apply_correction)
    workflow.add_node("supplier_extractor", supplier_extractor.extract_supplier_details)
    
    # NEW: Terminal State for Recursive Failures
    def human_fallback_queue(state: InvoiceState) -> Dict[str, Any]:
        logger.warning(f"CIRCUIT BREAKER: Invoice {state.get('image_path')} routed to HUMAN FALLBACK.")
        # Prepare best-effort output instead of blank status
        headers = state.get("global_modifiers", {})
        lines = state.get("line_items") or state.get("line_item_fragments", [])
        
        final_output = headers.copy()
        final_output["Line_Items"] = lines
        final_output["status"] = "HUMAN_REVIEW_REQUIRED"
        final_output["reason"] = "Mathematical Verification Loop Exhausted"
        
        return {"final_output": final_output}
    
    workflow.add_node("human_fallback", human_fallback_queue)
    
    # Define Edges
    workflow.add_edge(START, "surveyor")
    # workflow.add_edge("surveyor", "worker")
    
    def route_surveyor(state):
        plan = state.get("extraction_plan")
        if not plan:
            logger.error("Surveyor failed to generate a plan. Stopping execution to prevent infinite loop.")
            return "end"
        return "worker"

    workflow.add_conditional_edges(
        "surveyor",
        route_surveyor,
        {
            "worker": "worker",
            "end": END
        }
    )
    
    # Parallel Supplier Extraction (Start from Surveyor or Start? Start is fine, but Surveyor gives us image path reliably)
    # Let's run it parallel to Worker. Surveyor -> Supplier Extractor
    workflow.add_edge("surveyor", "supplier_extractor")
    workflow.add_edge("supplier_extractor", END) # It's a sidequest, effectively.
    
    workflow.add_edge("worker", "mapper")
    workflow.add_edge("mapper", "auditor")
    workflow.add_edge("auditor", "detective")
    workflow.add_edge("detective", "researcher") # WAS detective -> critic
    workflow.add_edge("researcher", "critic")
    
    # Conditional Feedback Loop
    def route_critic(state: InvoiceState):
        verdict = state.get("critic_verdict")
        # retry_counters maps node name/reason to count
        retry_count = state.get("retry_counters", {}).get("math_verification", 0)
        logger.info(f"Graph Decision: Verdict is {verdict} (Math Retry: {retry_count})")
        
        if verdict in ["APPROVE", "APPLY_MARKUP", "APPLY_MARKDOWN"]:
            return "solver"
        elif verdict == "RETRY_OCR":
            # Circuit Breaker: Check total accumulated retries from ALL nodes
            total_retries = state.get("retry_count", 0)
            if total_retries > 5:
                logger.error(f"CIRCUIT BREAKER: Total retries {total_retries} exceeded limit. Routing to Human Fallback.")
                return "human_fallback"
            return "worker"
            
        return "end"

    workflow.add_conditional_edges(
        "critic",
        route_critic,
        {
            "solver": "solver",
            "worker": "worker",
            "human_fallback": "human_fallback",
            "end": END
        }
    )
    
    workflow.add_edge("solver", END)
    workflow.add_edge("human_fallback", END)
    
    return workflow.compile()

# Global Compilation (Compile once on startup)
APP = build_graph()

async def run_extraction_pipeline(image_path: str, user_email: str, public_url: str = None, on_update: Callable = None):
    """
    Entry point to run the new graph-based pipeline.
    Initializes state and invokes the graph.
    """
    logger.info(f"Starting Extraction Graph for {image_path} (User: {user_email})")
    
    # User-friendly messages for AG-UI
    NODE_MESSAGES = {
        "surveyor": "Surveyor: Planning extraction zones...",
        "worker": "Worker: Extracting line items and table data...",
        "mapper": "Mapper: Identifying products in master catalog...",
        "auditor": "Auditor: Reconciling ledger and validating math...",
        "detective": "Detective: Investigating anomalies and tax gaps...",
        "researcher": "Researcher: Enriching items with web data...",
        "critic": "Critic: Finalizing verification and audit trail...",
        "solver": "Solver: Applying mathematical corrections...",
        "supplier_extractor": "Agent: Extracting supplier metadata..."
    }

    # APP is already compiled globally
    
    initial_state = {
        "image_path": image_path,
        "public_url": public_url,  # Inject public URL
        "user_email": user_email,
        "extraction_plan": [],
        "line_item_fragments": [],
        "global_modifiers": {},
        "final_output": {},
        "error_logs": [],
        "retry_counters": {"math_verification": 0},
        "error_history": []
    }
    
    # Initialize Langfuse Callback
    langfuse_handler = None
    try:
        langfuse_handler = CallbackHandler()
        # In newer versions, user_id can be set via attributes or metadata
        if hasattr(langfuse_handler, "user_id"):
            langfuse_handler.user_id = user_email
            
        callbacks = [langfuse_handler]
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse Callback: {e}")
        callbacks = []
    
    # Invoke Graph with Streaming
    result_state = initial_state
    async for event in APP.astream(initial_state, config={"callbacks": callbacks}, stream_mode="updates"):
        # The event is a dict: {node_name: {delta_state}}
        node_name = list(event.keys())[0]
        logger.info(f"Graph Update from {node_name}")
        
        # Trigger Callback for AG-UI
        if on_update:
            msg = NODE_MESSAGES.get(node_name, f"Executing {node_name}...")
            if asyncio.iscoroutinefunction(on_update):
                await on_update(node_name, msg)
            else:
                on_update(node_name, msg)

        # Merge delta into result_state
        result_state.update(event[node_name])
    
    # Extract final output
    final_output = result_state.get("final_output")

    # Capture Trace ID
    if langfuse_handler:
        try:
            # Try to get trace ID if available
            trace_id = None
            if hasattr(langfuse_handler, "get_trace_id"):
                trace_id = langfuse_handler.get_trace_id()
            elif hasattr(langfuse_handler, "trace") and langfuse_handler.trace:
                trace_id = langfuse_handler.trace.id
            elif hasattr(langfuse_handler, "last_trace_id"):
                 trace_id = langfuse_handler.last_trace_id

            if not trace_id:
                logger.warning(f"Failed to extract Trace ID. Handler attributes: {[a for a in dir(langfuse_handler) if not a.startswith('_')]}")
            
            if trace_id:
                logger.info(f"Langfuse Trace ID: {trace_id}")
                if final_output:
                    final_output["trace_id"] = trace_id
                else:
                    # Will be merged into constructed output later
                    result_state["trace_id"] = trace_id 
        except Exception as e:
            logger.warning(f"Failed to extract Trace ID: {e}")
    
    # FALLBACK: If pipeline ended without explicit Final Output (e.g. Retry Exhausted), construct it now
    if not final_output:
        logger.warning("Pipeline ended without Final Output. Constructing from State (Best Effort).")
        headers = result_state.get("global_modifiers", {})
        lines = result_state.get("line_items") or result_state.get("line_item_fragments", [])
        
        final_output = headers.copy()
        final_output["Line_Items"] = lines
    
    # ENSURE Standard_Item_Name mapping is present in final output
    if "Line_Items" in final_output:
        for item in final_output["Line_Items"]:
            if not item.get("Standard_Item_Name") and item.get("Product"):
                item["Standard_Item_Name"] = item["Product"]

    # MERGE Supplier Details into Final Output (HIGH PRIORITY)
    supplier_details = result_state.get("supplier_details")
    if supplier_details:
        logger.info(f"Merging Supplier Details into Output: {supplier_details}")
        final_output["supplier_details"] = supplier_details
        
        # Priority mapping for common header fields
        for field in ["Supplier_Name", "Invoice_No", "Invoice_Date", "GSTIN", "Address", "DL_No"]:
            if supplier_details.get(field):
                # Always prioritize the specialized agent's result if the main one is missing or default
                current_val = str(final_output.get(field, "")).strip().lower()
                if not current_val or current_val in ["unknown", "n/a", "none"]:
                    final_output[field] = supplier_details[field]
                    logger.info(f"Fallback Header Fix: Set {field} = {supplier_details[field]}")
        
    error_logs = result_state.get("error_logs", [])
    
    if error_logs:
        logger.warning(f"Pipeline completed with errors: {error_logs}")

    # Post-Processing: Smart Mapper (Auto-Fill from Master)
    if "Line_Items" in final_output:
        try:
            from src.domain.smart_mapper import enrich_line_items_from_master
            logger.info("Running Smart Mapper Enrichment...")
            line_items = final_output.get("Line_Items", [])
            enriched_items = await enrich_line_items_from_master(line_items, user_email)
            final_output["Line_Items"] = enriched_items
        except Exception as e:
            logger.error(f"Smart Mapper Failed: {e}")
        
    return final_output

def build_supply_chain_graph():
    """
    Constructs the Supply Chain Intelligence Graph.
    Flow: START -> Inventory Agent -> Forecasting Agent -> END
    """
    workflow = StateGraph(SupplyChainState)
    
    workflow.add_node("inventory_agent", inventory_agent.analyze_inventory)
    workflow.add_node("forecasting_agent", forecasting_agent.forecast_demand)
    
    workflow.add_edge(START, "inventory_agent")
    workflow.add_edge("inventory_agent", "forecasting_agent")
    workflow.add_edge("forecasting_agent", END)
    
    return workflow.compile()

# Global Compilation
SUPPLY_CHAIN_APP = build_supply_chain_graph()

async def run_supply_chain_intelligence(tenant_id: str, user_email: str):
    """
    Asynchronous entry point for supply chain analysis.
    Usually triggered after an invoice is confirmed.
    """
    logger.info(f"Triggering Supply Chain Intelligence for Tenant: {tenant_id}")
    
    initial_state = {
        "tenant_id": tenant_id,
        "user_email": user_email,
        "inventory_alerts": [],
        "demand_forecasts": []
    }
    
    try:
        result = await SUPPLY_CHAIN_APP.ainvoke(initial_state)
        logger.info(f"Supply Chain Intelligence Complete. Alerts: {len(result['inventory_alerts'])}, Forecasts: {len(result['demand_forecasts'])}")
        return result
    except Exception as e:
        logger.error(f"Supply Chain Intelligence failed: {e}")
        return None
