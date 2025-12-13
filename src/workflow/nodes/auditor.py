import google.generativeai as genai
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict

logger = logging.getLogger(__name__)

# Initialize Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.warning("GEMINI_API_KEY not found in environment variables.")

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
        desc = str(item.get("Original_Product_Description", "")).strip()
        net = str(item.get("Stated_Net_Amount", "")).strip()
        batch = str(item.get("Batch_No", "")).strip()
        
        signature = (desc, net, batch)
        
        if signature not in unique_items_map:
            unique_items_map[signature] = True
            deduped_line_items.append(item)
            
    logger.info(f"Auditor Deduplication: Reduced {len(line_items)} items to {len(deduped_line_items)} unique items.")

    # 1. Merge into Initial Draft
    draft_json = {
        "Line_Items": deduped_line_items,
        **global_modifiers
    }
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        sample_file = genai.upload_file(path=image_path, display_name="Auditor Check")
        
        prompt = f"""
        You are a Forensic Accountant. 
        Compare the Extracted Data (JSON) vs the Original Image.
        
        Input JSON:
        {json.dumps(draft_json, indent=2)}
        
        Task 1 (Double Tax Check / Logic Fix):
        - Calculate Sum(Net_Line_Amount) from the JSON.
        - Read Stated_Grand_Total from the Image Footer.
        - IF Calculated Total (e.g. 4000) is *significantly higher* than Stated Total (e.g. 3200):
            DIAGNOSIS: The column extracted as 'Stated_Net_Amount' was actually 'Taxable Value' (Pre-Tax) or 'Gross'.
            ACTION: Move the values from 'Stated_Net_Amount' to 'Raw_Taxable_Value' in the JSON, and set 'Stated_Net_Amount' to 0 (to let downstream normalization recalculate).
            
        Task 2 (Missing Discount):
        - If the Image Footer shows 'Less: Cash Discount' or similar, but 'Global_Discount_Amount' is 0 or missing in JSON, extract it strictly now.
        
        Output:
        Return the CORRECTED JSON entirely. Ensure 'Line_Items' and footer fields are present.
        """
        
        response = model.generate_content([prompt, sample_file])
        text = response.text.replace("```json", "").replace("```", "").strip()
        corrected_json = json.loads(text)
        
        logger.info("Auditor verification complete.")
        return {"final_output": corrected_json}

    except Exception as e:
        logger.error(f"Auditor failed: {e}")
        # Fallback: Return the un-audited draft if audit fails
        return {
            "final_output": draft_json,
            "error_logs": [f"Auditor Failed: {str(e)}"]
        }
