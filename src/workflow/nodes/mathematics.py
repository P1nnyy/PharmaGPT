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
    
    logger.info(f"Mathematics: Applying correction factor {factor:.4f} to {len(lines)} items.")
    
    updated_lines = []
    for item in lines:
        try:
            raw_net = float(item.get("Stated_Net_Amount") or 0)
            qty = float(item.get("Raw_Quantity") or 1)
            if qty <= 0: qty = 1.0
            
            # 1. Adjust Total Cost to match the Check (Landed Cost)
            new_net = round(raw_net * factor, 2)
            
            # 2. Recalculate Unit Rate
            # This is the most critical number for the shop user!
            new_rate = round(new_net / qty, 2)
            
            item["Stated_Net_Amount"] = new_net
            # Using Landed_Cost_Per_Unit as it is defined in RawLineItem schema for pass-through
            item["Landed_Cost_Per_Unit"] = new_rate 
            # Also setting the user-requested key for clarity/legacy
            item["Calculated_Cost_Price_Per_Unit"] = new_rate
            
            item["Logic_Note"] = f"Auto-Adjusted by {factor:.4f} (Global Tax/Discount)"
            
            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Math Fix Failed on item: {e}")
            updated_lines.append(item)
        
    return {
        "line_item_fragments": updated_lines,
        "final_output": {"Line_Items": updated_lines} # Ready for Frontend
    }
