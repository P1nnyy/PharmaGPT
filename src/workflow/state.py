from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated
import operator

class InvoiceState(TypedDict):
    """
    State object for the Invoice Extraction LangGraph workflow.
    Holds data as it flows between the Surveyor, Workers, and Auditor.
    """
    image_path: str
    extraction_plan: List[Dict[str, Any]]  # Zones identified by Surveyor
    
    # Fragments from parallel workers (e.g. Primary Table, Secondary Table)
    # operator.add ensures these lists are merged, not overwritten
    line_item_fragments: Annotated[List[Dict[str, Any]], operator.add]
    
    # NEW: Raw Text from Worker (Stage 1) - Before Mapping
    raw_text_rows: Annotated[List[str], operator.add]
    
    # Unified, Deduplicated Line Items (Output of Auditor)
    # Default behavior is replace/overwrite, which is what we want for this stage
    line_items: List[Dict[str, Any]]
    
    anchor_totals: Dict[str, float]  # Stores "Grand Total" from Footer Agent (The Truth)
    critic_verdict: str              # Decision: "APPROVE", "APPLY_MARKUP", "APPLY_MARKDOWN", "RETRY_OCR"
    correction_factor: float         # Ratio to apply for markup/markdown
    retry_count: int                 # Safety counter for infinite loops
    
    global_modifiers: Dict[str, Any]      # Invoice-level data (Global Discount, Freight)
    final_output: Dict[str, Any]          # Final cleaned JSON for API
    
    # Log of logic decisions vs failures
    error_logs: Annotated[List[str], operator.add]
    
    # Smart Feedback from Critic/Auditor to Worker (for Retries)
    feedback_logs: Annotated[List[str], operator.add]
    
    # NEW: Dedicated Supplier Details (Parallel Pipeline)
    supplier_details: Dict[str, Any]
    
    # Context
    user_email: str
