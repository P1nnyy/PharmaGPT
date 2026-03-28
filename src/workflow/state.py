from typing import TypedDict, List, Dict, Any, Optional, Annotated
from typing_extensions import Annotated
import operator

class InvoiceState(TypedDict):
    """
    State object for the Invoice Extraction LangGraph workflow.
    Holds data as it flows between the Surveyor, Workers, and Auditor.
    """
    image_path: str
    public_url: str  # URL for Frontend Display (R2/S3)
    extraction_plan: List[Dict[str, Any]]  # Zones identified by Surveyor
    
    # Fragments from parallel workers (e.g. Primary Table, Secondary Table)
    # operator.add ensures these lists are merged, not overwritten
    line_item_fragments: Annotated[List[Dict[str, Any]], operator.add]
    
    # NEW: Raw Text from Worker (Stage 1) - Before Mapping
    raw_text_rows: List[str]
    
    # Unified, Deduplicated Line Items (Output of Auditor)
    # Default behavior is replace/overwrite, which is what we want for this stage
    line_items: List[Dict[str, Any]]
    
    anchor_totals: Dict[str, float]  # Stores "Grand Total" from Footer Agent (The Truth)
    critic_verdict: str              # Decision: "APPROVE", "APPLY_MARKUP", "APPLY_MARKDOWN", "RETRY_OCR"
    correction_factor: float         # Ratio to apply for markup/markdown
    retry_count: Annotated[int, operator.add]  # Total Graph Loops (Circuit Breaker)
    
    global_modifiers: Dict[str, Any]      # Invoice-level data (Global Discount, Freight)
    final_output: Dict[str, Any]          # Final cleaned JSON for API
    
    # Log of logic decisions vs failures
    error_logs: Annotated[List[str], operator.add]
    
    # NEW: Automated Logic History (Circuit Breaker)
    # retry_counters: Maps node name/reason to count
    # error_history: Running log of all validation failures
    retry_counters: Annotated[Dict[str, int], operator.ior]
    error_history: Annotated[List[str], operator.add]
    
    # Context
    user_email: str
    trace_id: Optional[str]               # Langfuse Trace ID for debugging
    supplier_details: Dict[str, Any]      # Specialized extraction (GST, DL, Address)
    
    # --- Observability & Tracking ---
    # error_metadata: Stores specific error codes and context
    # reconciliation_stats: Stores mathematical variances for Prometheus
    error_metadata: Annotated[Dict[str, Any], operator.ior]
    reconciliation_stats: Annotated[Dict[str, Any], operator.ior]
    # New tracking pockets for Grafana
    errorMetadata: dict
    reconciliation_stats: dict
    retry_counters: Annotated[dict, operator.ior]
    error_history: Annotated[list, operator.add]

class SupplyChainState(TypedDict):
    """
    State for the post-processing Supply Chain Intelligence workflow.
    """
    tenant_id: str
    user_email: str
    inventory_alerts: List[Dict[str, Any]]
    demand_forecasts: List[Dict[str, Any]]
    trace_id: Optional[str]
