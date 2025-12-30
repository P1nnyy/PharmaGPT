from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("solver")

def apply_correction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Applies the Critic's correction factor to all line items.
    This creates the "Landed Cost" which is what the shop actually pays.
    """
    # PREFER: 'line_items' (Clean)
    # FALLBACK: 'line_item_fragments' (Dirty)
    lines = state.get("line_items") or state.get("line_item_fragments", [])
    
    correction_factor = state.get("correction_factor", 1.0)
    
    # USER REQUEST: Always Apply Global Discounts/Tax, even if small.
    # We removed the ignore block (0.9 < factor < 1.1) to ensure the landing cost
    # accurately reflects the final bill value including global discounts.
    if correction_factor == 1.0:
        logger.info("Solver: Correction Factor is 1.0. No adjustments needed.")
    else:
        logger.info(f"Solver: Applying Final Correction Factor {correction_factor} to {len(lines)} items.")
    
    updated_lines = []
    for item in lines:
        try:
            # UPDATED: Use Amount OR Stated Net
            raw_net = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            qty = float(item.get("Qty") or 1)
            
            # 1. Adjust Total Cost to match the Check (Landed Cost)
            new_net = round(raw_net * correction_factor, 2)
            
            # 2. Recalculate Unit Rate (Landing Cost)
            # This is the most critical number for the shop user!
            new_rate = round(new_net / qty, 2) if qty > 0 else 0
            
            item["net_amount"] = new_net
            item["landing_cost"] = new_rate
            item["Logic_Note"] = item.get("Logic_Note", "") + f" [Solver: {correction_factor:.4f}]"
            
            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Error: {e}")
            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Error: {e}")
            updated_lines.append(item)
        
    # Reconstruct Final Output
    # We need to merge the Headers/Footers (Global Modifiers) with the reconciled Line Items
    headers = state.get("global_modifiers", {})
    metadata = state.get("header_data", {})
    
    final_json = headers.copy()
    final_json["metadata"] = metadata
    final_json["Line_Items"] = updated_lines
    
    return {
        "line_items": updated_lines, 
        "final_output": final_json # Complete object with Headers + Reconciled Lines
    }
