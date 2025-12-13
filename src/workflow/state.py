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
    
    global_modifiers: Dict[str, Any]      # Invoice-level data (Global Discount, Freight)
    final_output: Dict[str, Any]          # Final cleaned JSON for API
    
    # Log of logic decisions vs failures
    error_logs: Annotated[List[str], operator.add]
