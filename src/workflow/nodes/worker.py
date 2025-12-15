import google.generativeai as genai
import asyncio
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.config_loader import load_column_aliases
from src.utils.logging_config import get_logger
from src.utils.image_processing import preprocess_image_for_ocr
import tempfile

logger = get_logger(__name__)

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

async def extract_from_zone(model, image_file, zone: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper function to process a single zone.
    Returns a dict with specific keys based on zone type.
    """
    zone_type = zone.get("type", "table")
    description = zone.get("description", "")
    
    try:
        if "table" in zone_type.lower():
            # Scenario A: Table Extraction
            # Inject Column Aliases
            aliases = load_column_aliases().get("global_column_aliases", {})
            
            prompt = f"""
            Target Zone: {description}
            
            TASK: EXTRACT RAW TABLE DATA (VERBATIM).
            
            Instructions:
            1. Look at the table in this image.
            2. Extract EVERY row of text you see.
            3. Format as a PIPE-SEPARATED Table (Markdown format).
            4. Include headers if visible.
            5. Do NOT try to rename columns. Capture exact text like "Pcode", "Qty", "N.Rate".
            
            IMPORTANT:
            - **DENSE ROWS**: If you see "Vaporub 5gm" and "Vaporub 10gm" on separate lines, WRITE THEM ON SEPARATE LINES.
            - **NO SKIPPING**: Include "Offer", "Scheme", "Free", "Total" rows.
            - **NO MERGING**: Do not merge distinct visual rows.
            
            Output Format Example:
            | Description | Pcode | Qty | Rate | Amount |
            | Vicks 5gm | 80811 | 1 | 100 | 100 |
            
            Return ONLY the markdown table string. No JSON.
            """
            response = await model.generate_content_async([prompt, image_file])
            text = response.text.strip()
            # Return raw text wrapped in a dict
            return {"type": "raw_text", "data": [text]} 
            
        elif "footer" in zone_type.lower():
            # Scenario B: Footer Extraction
            prompt = f"""
            Target Zone: {description}
            
            Task: Extract global financial fields from this section. Ignore line items.
            
            Fields to Extract:
            - Global_Discount_Amount (Look for 'Cash Discount', 'CD', 'Less Discount')
            - Freight_Charges
            - Round_Off
            - Stated_Grand_Total (The final 'Net Payable' or 'Grand Total'). This is the **ANCHOR** truth for the invoice.
            
            CRITICAL:
            - The 'Stated_Grand_Total' is the most important field. If it is ambiguous, look for the double-bolded or final bottom-right figure.
            
            Return JSON:
            {{
                "Global_Discount_Amount": float,
                "Freight_Charges": float,
                "Round_Off": float,
                "Stated_Grand_Total": float
            }}
            """
            response = await model.generate_content_async([prompt, image_file])
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return {"type": "modifiers", "data": data}
            
        elif "header" in zone_type.lower():
            # Scenario C: Header Extraction
            prompt = f"""
            Target Zone: {description}
            
            Task: Extract invoice header details.
            
            Fields:
            - Supplier_Name
            - Invoice_No
            - Invoice_Date (YYYY-MM-DD format preferred)
            
            NEGATIVE CONSTRAINTS (STRICTLY IGNORE):
            - IGNORE "Bank Details".
            - IGNORE "Previous Balance" or "Outstanding" tables.
            - **Allowed**: You MAY look at Tax Columns ONLY if they contain the "Net Amount" or "Total".
            
            Return JSON:
            {{
                "Supplier_Name": "string",
                "Invoice_No": "string",
                "Invoice_Date": "string"
            }}
            """
            response = await model.generate_content_async([prompt, image_file])
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return {"type": "modifiers", "data": data}
            
    except Exception as e:
        logger.error(f"Failed to extract zone {zone}: {e}")
        return {"type": "error", "error": str(e)}

    return {}

async def execute_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Worker Node.
    Executes the extraction plan concurrently.
    """
    image_path = state.get("image_path")
    plan = state.get("extraction_plan", [])
    
    if not image_path or not plan:
        return {"error_logs": ["Worker: Missing image path or extraction plan."]}

    # Prepare Model and File
    # Note: For async, we should ideally reuse the file resource if possible, 
    # but the python SDK handles upload_file synchronously usually. 
    # We'll upload once synchronously (fast enough) or check if we can pass the path.
    # The 'generate_content_async' accepts path or file object.
    
    # Re-uploading for simplicity in this node context, or assuming state has a file handle?
    # State only has path. We'll upload here.
    # Preprocess Image
    try:
        logger.info("Worker: Preprocessing image (Perspective Warp + Binarization)...")
        processed_bytes = preprocess_image_for_ocr(image_path)
        
        # Save to temp file for Gemini Upload
        # Gemini API needs a path or file-like object with name. 
        # Using tempfile to be safe.
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(processed_bytes)
            tmp_image_path = tmp_file.name
            
        logger.info(f"Worker: Processed image saved to {tmp_image_path}")
        
    except Exception as e:
        logger.error(f"Worker warning: Preprocessing failed ({e}). Using original image.")
        tmp_image_path = image_path

    try:
        # Upload the PROCESSED image
        sample_file = genai.upload_file(path=tmp_image_path, display_name="Worker Extraction")
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Check Retry State
        retry_count = int(state.get("retry_count", 0))
        
        if retry_count > 0:
            logger.info(f"Worker: Retry Mode {retry_count}. Switching to FULL PAGE EXTRACTION.")
            
            # Retrieve Feedback from Critic (if any)
            feedback_logs = state.get("feedback_logs", [])
            feedback_context = ""
            if feedback_logs:
                latest_feedback = feedback_logs[-1]
                feedback_context = f"\n            PREVIOUS ATTEMPT FAILED. CRITIC FEEDBACK: {latest_feedback}\n            PLEASE CORRECT THIS ERROR."
            
            # FALLBACK STRATEGY: SCAN WHOLE PAGE AS RAW TABLE
            prompt = f"""
            CRITICAL RECOVERY MODE:
            The previous zone-based extraction failed. 
            Now, analyze the ENTIRE document image.
            
            TASK: EXTRACT ALL TABLES AS RAW MARKDOWN.
            
            Instructions:
            1. Find the main table with Products, Qty, Amounts.
            2. Convert it VISUALLY into a Pipe-Separated Markdown table.
            3. **Do not merge rows**. Keep every single line item separate.
            4. Capture exact headers like "Pcode", "Rate", "Amount".
            
            Output ONLY the table.
            """
            
            response = await model.generate_content_async([prompt, sample_file])
            text = response.text.strip()
            
            raw_text_rows = [text] 
            
            # Skip old logic
            line_item_fragments = []
            # Assumption: Invoice items are listed in order. If HSN is missing, it's likely same as above.
            logger.info("DEBUG: Starting HSN Forward Fill...")
            print("DEBUG: Starting HSN Forward Fill...")
            
            last_valid_hsn = None
            for i, item in enumerate(line_item_fragments):
                curr_hsn = item.get("HSN")
                desc = item.get("Product")
                
                logger.info(f"DEBUG: Item {i} '{desc}' | HSN: {curr_hsn} | Last: {last_valid_hsn}")
                
                if curr_hsn and str(curr_hsn).strip().lower() not in ["", "none", "null", "n/a"]:
                    last_valid_hsn = curr_hsn
                elif last_valid_hsn:
                    # Fill missing HSN from previous valid one
                    item["HSN"] = last_valid_hsn
                    logger.info(f"Worker: Forward Filled HSN {last_valid_hsn} for '{desc}'")
                    print(f"DEBUG: Filled HSN {last_valid_hsn} for {desc}")

            global_modifiers = {} 
            anchor_totals = {}
            error_logs = []
            
        else:
            # NORMAL MODE: ZONE BASED
            tasks = []
            for zone in plan:
                tasks.append(extract_from_zone(model, sample_file, zone))
                
            # Run Concurrent
            results = await asyncio.gather(*tasks)
            
            # Aggregate Results
            line_item_fragments = [] # Worker no longer produces these directly
            raw_text_rows = [] 
            global_modifiers = {}
            anchor_totals = {}
            error_logs = []
            
            for res in results:
                if res.get("type") == "raw_text":
                    rows = res.get("data", [])
                    raw_text_rows.extend(rows)
                elif res.get("type") == "modifiers":
                    mods = res.get("data", {})
                    global_modifiers.update(mods)
                    
                    # Capture Anchor for Critic
                    if "Stated_Grand_Total" in mods and mods["Stated_Grand_Total"]:
                        try:
                            anchor_totals["Stated_Grand_Total"] = float(mods["Stated_Grand_Total"])
                        except:
                            pass
                            
                elif res.get("type") == "error":
                    error_logs.append(f"Zone Extraction Failed: {res.get('error')}")
                
        # Increment Retry Count
        new_retry_count = retry_count + 1
        
        # ---------------------------------------------------------
        # GLOBAL POST-PROCESSING (Run for BOTH Zone and Fallback modes)
        # ---------------------------------------------------------
        
        # 1. HSN Forward Fill
        # Use 'line_item_fragments' because that's what we return.
        if line_item_fragments:
            logger.info("Worker: Starting Global HSN Forward Fill...")
            last_valid_hsn = None
            for item in line_item_fragments:
                curr_hsn = item.get("HSN")
                
                # Check for validity
                if curr_hsn and str(curr_hsn).strip().lower() not in ["", "none", "null", "n/a"]:
                    last_valid_hsn = curr_hsn
                elif last_valid_hsn:
                    # Fill
                    item["HSN"] = last_valid_hsn
                    # Only log occasionally to avoid spam
                    # logger.info(f"Worker: Filled {last_valid_hsn}")

        logger.info(f"Worker: Extraction Complete. Retry {retry_count} -> {new_retry_count}. Items Found: {len(line_item_fragments)}")

        return {
            "line_item_fragments": [], # Empty, because Mapper will fill this later
            "raw_text_rows": raw_text_rows,
            "global_modifiers": global_modifiers,
            "anchor_totals": anchor_totals,
            "error_logs": error_logs,
            "retry_count": new_retry_count
        }
        
    except Exception as e:
        logger.error(f"Worker Master Error: {e}")
        return {"error_logs": [f"Worker Execution Failed: {str(e)}"]}
