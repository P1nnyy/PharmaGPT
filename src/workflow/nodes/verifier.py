from typing import Dict, Any, List
import logging
import json
import os
import google.generativeai as genai
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("verifier")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

async def verify_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Verifier Node.
    Stage 4 of Extraction (Optional / Smart).
    
    Identifies 'Suspicious' items (where Math was forced, or low confidence)
    and performs a Targeted Visual Check using the LLM + Image.
    """
    logger.info("Verifier: Starting visual verification pass...")
    
    image_path = state.get("image_path")
    line_items = state.get("line_items", [])
    
    if not image_path or not line_items:
        return {"verification_logs": ["Verifier: Missing data. Skipping."]}

    # 1. Identify Suspicious Items
    suspicious_items = []
    
    for i, item in enumerate(line_items):
        # Criteria A: Auditor "Forced" a fix
        logic_note = item.get("Logic_Note", "")
        
        # Criteria B: Math Mismatch (still lingering?)
        try:
            qty = float(item.get("Qty") or 0)
            rate = float(item.get("Rate") or 0)
            amt = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            
            expected = qty * rate
            mismatch = abs(expected - amt) > max(1.0, amt * 0.1) # 10% tolerance
        except:
            mismatch = False

        if "Fix]" in logic_note or "Calc Qty" in logic_note or mismatch:
            # Check if we already have a specific rule for this?
            # Or just verify it.
            suspicious_items.append(i)
            logger.info(f"Verifier: Flagged '{item.get('Product')}' for visual check. Reason: {logic_note or 'Math Mismatch'}")

    if not suspicious_items:
        logger.info("Verifier: No suspicious items found. Trusting extraction.")
        return {"verification_logs": ["Verifier: No suspicious items. Passed."]}

    # 2. Perform Visual Verification (Batch or Sequential)
    # We'll do a single "Batch Verify" call to save time/tokens if there are multiple.
    
    items_to_verify_str = ""
    for idx in suspicious_items:
        item = line_items[idx]
        items_to_verify_str += f"- Item: '{item.get('Product', 'Unknown')}' | Current Qty: {item.get('Qty')} | Current Rate: {item.get('Rate')} | Total Amount: {item.get('Amount')}\n"

    prompt = f"""
    I have extracted some data from this invoice, but my automated checks flagged potential errors.
    Please LOOK CAREFULLY at the image for the following specific items and VERIFY their Quantity and Rate.
    
    ITEMS TO VERIFY:
    {items_to_verify_str}
    
    TASK:
    For each item, find it in the image.
    1. Read the explicit 'Quantity' column. Watch out for 'Free' quantities or split columns (e.g. 10+2).
    2. Read the 'Rate' or 'Price' column.
    3. Calculate if Qty * Rate matches the Amount.
    
    OUTPUT JSON ONLY:
    {{
        "corrections": [
            {{
                "Product": "exact product name matched",
                "Correct_Qty": float,
                "Correct_Rate": float,
                "Reason": "Found column X which says Y..."
            }}
        ]
    }}
    If the original values are correct, return them as the 'Correct' values.
    """
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Upload file properly if needed, but assuming path works for now or re-upload
        # Re-using the logic from worker for upload might be safer
        # For speed, let's try direct path (GenAI python SDK handles it often?)
        # Actually standard practice is upload_file
        
        sample_file = genai.upload_file(path=image_path, display_name="Verifier Check")
        
        response = await model.generate_content_async([prompt, sample_file])
        text = response.text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(text)
        corrections = data.get("corrections", [])
        
        verification_logs = []
        
        for correction in corrections:
            prod_name = correction.get("Product")
            corr_qty = float(correction.get("Correct_Qty") or 0)
            corr_rate = float(correction.get("Correct_Rate") or 0)
            reason = correction.get("Reason", "")
            
            # Find the match in our line items
            # Simple substring match or fuzzy?
            # We know the list we sent, so likely exact match or close.
            
            matched = False
            for idx in suspicious_items:
                original_item = line_items[idx]
                # Compare names
                if prod_name.lower() in str(original_item.get("Product")).lower() or \
                   str(original_item.get("Product")).lower() in prod_name.lower():
                    
                    # Updates
                    old_qty = float(original_item.get("Qty") or 0)
                    if abs(old_qty - corr_qty) > 0.1:
                        logger.info(f"Verifier: CORRECTION! '{prod_name}' Qty {old_qty} -> {corr_qty}. Reason: {reason}")
                        original_item["Qty"] = corr_qty
                        original_item["Standard_Quantity"] = int(corr_qty) # Sync
                        original_item["Logic_Note"] += f" [Verifier: Fixed Qty ({reason})]"
                    
                    old_rate = float(original_item.get("Rate") or 0)
                    if abs(old_rate - corr_rate) > 0.1:
                         logger.info(f"Verifier: CORRECTION! '{prod_name}' Rate {old_rate} -> {corr_rate}. Reason: {reason}")
                         original_item["Rate"] = corr_rate
                         original_item["Logic_Note"] += f" [Verifier: Fixed Rate]"
                         
                    matched = True
                    verification_logs.append(f"Verified '{prod_name}': {reason}")
            
            if not matched:
                logger.warning(f"Verifier provided correction for '{prod_name}' but couldn't match to original list.")

        return {
            "line_items": line_items, # Updated list
            "verification_logs": verification_logs
        }
        
    except Exception as e:
        logger.error(f"Verifier Failed: {e}")
        return {"verification_logs": [f"Verifier Error: {e}"]}
