from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict

logger = logging.getLogger(__name__)

def apply_correction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Applies the Critic's correction factor to all line items.
    This creates the "Landed Cost" which is what the shop actually pays.
    """
    factor = state.get("correction_factor", 1.0)
    lines = state.get("line_item_fragments", [])
    
    updated_lines = []
    for item in lines:
        try:
            raw_net = float(item.get("Stated_Net_Amount") or 0)
            qty = float(item.get("Raw_Quantity") or 1)
            
            # 1. Adjust Total Cost to match the Check (Landed Cost)
            new_net = round(raw_net * factor, 2)
            
            # 2. Recalculate Unit Rate
            # This is the most critical number for the shop user!
            new_rate = round(new_net / qty, 2) if qty > 0 else 0
            
            item["Net_Line_Amount"] = new_net
            item["Calculated_Cost_Price_Per_Unit"] = new_rate
            item["Logic_Note"] = f"Auto-Adjusted by {factor:.4f} (Global Tax/Discount)"
            
            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Error: {e}")
            updated_lines.append(item)
        
    return {
        "line_item_fragments": updated_lines,
        "final_output": {"Line_Items": updated_lines} # Ready for Frontend
    }
