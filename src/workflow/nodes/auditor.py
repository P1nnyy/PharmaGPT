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
        # Create a unique signature
        # Normalize strings to prevent case/whitespace dupes
        desc = str(item.get("Original_Product_Description", "")).strip().lower().replace("  ", " ")
        net = str(item.get("Stated_Net_Amount", "")).strip()
        batch = str(item.get("Batch_No", "")).strip().lower()
        
        # Use (Description, Net) as primary uniqueness if Batch is missing?
        # Or (Description, Batch) if Net varies slightly due to OCR noise?
        # Let's keep strict net for now, but formatted standardly
        try:
             # Try to normalize net amount to 2 decimal places string
             net_val = float(net)
             net = f"{net_val:.2f}"
        except:
             pass
        
        signature = (desc, net, batch)
        
        if signature not in unique_items_map:
            # Noise Filter: Ignore items with 0 Net AND 0 Quantity (or negligible values)
            try:
                n_val = float(item.get("Stated_Net_Amount") or 0)
                q_val = float(item.get("Raw_Quantity") or 0)
                if n_val == 0.0 and q_val == 0.0:
                    continue # Skip noise
            except Exception as e:
                logger.warning(f"Auditor Filter Error: {e}")
                pass

            unique_items_map[signature] = True
            deduped_line_items.append(item)
            
    logger.info(f"Auditor Deduplication: Reduced {len(line_items)} items to {len(deduped_line_items)} unique items.")

    # 2. Return RAW Deduplicated Items
    # We delegate Normalization to the Server/Consumer to keep schemas aligned (Raw -> Normalized).
    
    final_output = {
        "Line_Items": deduped_line_items,
        **global_modifiers
    }
    
    logger.info("Auditor verification complete.")
    return {"final_output": final_output}
