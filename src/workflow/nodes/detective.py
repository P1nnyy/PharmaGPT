import google.generativeai as genai
import json
import os
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("detective")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

from langfuse import observe

@observe(name="detective_investigation")
def detective_work(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Detective Node.
    Runs AFTER Auditor.
    Inspects line items for missing critical data (Batch).
    Performs TARGETED re-extraction for specific missing items.
    """
    image_path = state.get("image_path")
    line_items = state.get("line_items", []) # Auditor outputs 'line_items'
    
    if not image_path or not line_items:
        return {}

    logger.info("Detective: Starting investigation for missing details...")
    
    updated_items = []
    investigation_count = 0
    
    # Load Image once
    try:
        sample_file = genai.upload_file(image_path, mime_type="image/jpeg")
    except Exception as e:
        logger.error(f"Detective: Failed to upload image: {e}")
        return {}

    model = genai.GenerativeModel("gemini-2.0-flash")

    for item in line_items:
        # Check if Batch No is missing
        batch_no = item.get("Batch")
        description = item.get("Product", "Unknown Item")
        
        is_missing = not batch_no or batch_no in ["", "None", "null", "N/A"]
        
        if is_missing:
            investigation_count += 1
            logger.info(f"Detective: Investigating missing Batch for '{description}'")
            
            # Formulate Targeted Prompt
            prompt = f"""
            You are a DATA DETECTIVE. Your goal is to find the Batch Number for a specific item in this invoice image.
            
            Target Item: "{description}"
            
            INSTRUCTIONS:
            1. Scan the invoice specifically for this item.
            2. Look for columns labeled **"Pcode"**, **"Product Code"**, **"Code"**, **"Lot"**, **"Batch"**, or **"B.No"**.
            3. CRITICAL: Also look at the row IMMEDIATELY BELOW the product name. It might be hidden in an "Offer" or "Scheme" line.
            4. If found, return ONLY the alphanumeric Batch Number.
            5. If NOT found, return "null".
            
            Output Format: JSON {{ "Batch": "value" }}
            """
            
            try:
                response = model.generate_content([sample_file, prompt])
                text = response.text.replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                
                found_batch = result.get("Batch")
                
                # Validation: Check if found_batch matches HSN
                hsn_code = str(item.get("HSN", "")).replace(" ", "")
                batch_clean = str(found_batch).replace(" ", "")
                
                is_hsn = (
                    batch_clean == hsn_code or
                    batch_clean.startswith("3004") or 
                    batch_clean.startswith("9601") or
                    batch_clean.startswith("9619")
                )
                
                if found_batch and found_batch.lower() != "null" and not is_hsn:
                    logger.info(f"Detective: SUCCESS! Found Batch '{found_batch}' for '{description}'")
                    item["Batch"] = found_batch
                    item["Logic_Note"] = item.get("Logic_Note", "") + " [Detective: Recovered Batch]"
                elif is_hsn:
                     logger.warning(f"Detective: Rejected HSN-like Batch '{found_batch}' for '{description}'")
                else:
                    logger.info(f"Detective: Could not find batch for '{description}'.")
                    
            except Exception as e:
                logger.warning(f"Detective Interface Error: {e}")
        
        updated_items.append(item)

    if investigation_count == 0:
        logger.info("Detective: No missing batches found. Case closed.")
    else:
        logger.info(f"Detective: Investigation complete. Checked {investigation_count} items.")

    return {"line_items": updated_items}
