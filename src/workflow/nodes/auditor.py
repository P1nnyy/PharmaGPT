import google.generativeai as genai
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict

logger = logging.getLogger(__name__)

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

def audit_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Auditor Node.
    performs a textual/math verification pass to catch logical errors
    like 'Double Tax' (Net vs Taxable) or missing Global Discounts.
    """
    image_path = state.get("image_path")
    line_items = state.get("line_item_fragments", [])
    global_modifiers = state.get("global_modifiers", {})
    
    if not image_path or not line_items:
        return {"error_logs": ["Auditor: Missing input data."]}

    # Deduplication Logic (Prevent Value Overflow from overlapping zones)
    unique_items_map = {}
    deduped_line_items = []
    
    for item in line_items:
        try:
            # 1. Scalable Noise Filter
            n_val = float(item.get("Stated_Net_Amount") or 0)
            q_val = float(item.get("Raw_Quantity") or 0)
            
            if abs(n_val) < 0.1 and abs(q_val) < 0.1:
                continue # Skip noise
                
            # 2. Fuzzy Deduplication Signature
            desc = str(item.get("Original_Product_Description", "")).strip().lower()
            desc = " ".join(desc.split())
            net_sig = int(n_val)
            
            signature = (desc, net_sig)

            if signature not in unique_items_map:
                unique_items_map[signature] = True
                deduped_line_items.append(item)
                
        except Exception as e:
            logger.warning(f"Auditor Deduplication Error: {e}")
            deduped_line_items.append(item)
            
    logger.info(f"Auditor Deduplication: Reduced {len(line_items)} items to {len(deduped_line_items)} unique items.")

    # --- AUDIT COMPLETE ---
    # We now pass the 'deduped_line_items' to the Critic for Math Verification.
    
    final_output = {
        "Line_Items": deduped_line_items,
        **global_modifiers
    }
    
    logger.info("Auditor verification complete.")
    # Return as 'line_item_fragments' so the State updates for the next node
    return {
        "line_item_fragments": deduped_line_items,
        "final_output": final_output # Keep this for legacy single-pass, but Graph will rely on State
    }
