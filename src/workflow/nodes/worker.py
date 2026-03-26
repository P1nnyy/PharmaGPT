from src.services.ai_client import manager
import asyncio
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.config_loader import load_column_aliases
from src.utils.logging_config import get_logger
from src.utils.image_processing import preprocess_image_for_ocr
from src.utils.ai_retry import ai_retry
import tempfile

logger = get_logger(__name__)

@ai_retry
async def extract_from_zone(unused_model, image_file, zone: Dict[str, Any]) -> Dict[str, Any]:
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
            # Flatten aliases for prompt context
            alias_context = "\n".join([f"- **{k}**: {', '.join(v)}" for k, v in aliases.items()])
            
            prompt = f"""
            Target Zone: {description}
            
            TASK: EXTRACT RAW TABLE DATA (VERBATIM).
            
            **KNOWN COLUMN HEADERS (LOOK FOR THESE):**
            {alias_context}
            
            Instructions:
            1. Look at the table in this image.
            2. Extract EVERY row of text you see.
            3. Format as a PIPE-SEPARATED Table (Markdown format).
            4. Include headers if visible.
            5. **Do not simplify**: If a cell contains "Batch: A123", write "Batch: A123". Do not just write "Batch". Capture ALL text.
            
            CRITICAL TABLE PARSING RULES:
            - **ROW ALIGNMENT (THE MOST IMPORTANT RULE)**: You MUST preserve the exact row alignment. 
                - **DO NOT SHIFT COLUMNS VERTICALLY**. 
                - If "Product A" is on Line 1, its Batch, Expiry, and Rate MUST be on Line 1. Do not pull "Batch" from Line 2 up to Line 1.
                - Treat horizontal grid lines as **HARD WALLS**. Data cannot cross these lines.
            - **Split "Qty + Free"**: If you see a column "Qty+Free" like "10+2", SPLIT IT into two columns "Qty" and "Free" or capture as "10+2" in one cell. DO NOT shift data left/right.
            - **Prices are NOT Quantities**: "MRP" (e.g. 200.00) and "Rate" (e.g. 150.00) are typically larger than "Qty" (e.g. 1, 10). Do not mix them up.
            - **IGNORE UFC/FACTOR**: Do not extract "UFC", "Factor", "Case" columns as "MRP". Identify them as "Pack" or "Unit" if needed, but NEVER as a price column.
            
            IMPORTANT:
            - **DENSITY**: If a cell has multiple lines (e.g. "Batch\n123"), capture BOTH lines in the markdown cell (use <br> or space).
            - **DUPLICATES**: If the Exact Same Item appears on multiple lines (e.g. "Dolo 650" twice), LIST IT TWICE. Do not combine them.
            - **NO SKIPPING**: Include "Offer", "Scheme", "Free", "Total" rows.
            - **NO MERGING**: Do not merge distinct visual rows.
            - **COLUMNS**: Aggressively look for "Amount", "Value", "Total". 
            - **AMOUNT RULE**: The "Amount" column is the PRE-TAX, PRE-GLOBAL-DISCOUNT value (Rate * Qty).
            - **MANUFACTURER**: Aggressively look for "Mfr", "CMPNY", "Co", "Make" columns. extract them!
            
            NEGATIVE CONSTRAINTS (CRITICAL):
            - **IGNORE "Initiative Name" Tables**: Do NOT extract tables with headers like "Initiative Name", "Product Batch No", "Free Product". These are schemes, not line items.
            - **IGNORE "Tax" Breakdowns**: Do not extract GST summary tables.
            - **IGNORE "Bank Details"**: Do not extract bank info as rows.
            - **IGNORE "Header Info"**: Do not extract Supplier Name, Invoice No, or Date as a table row. ONLY extract the Product Line Items.
            
            Output Format Example:
            | Description | Pcode | Qty | Rate | Amount | Net Amount |
            | Vicks 5gm | 80811 | 1 | 100 | 100 | 112 |
            
            Return ONLY the markdown table string. No JSON.
            """
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt, image_file]
            )
            text = response.text.strip()
            # Return raw text wrapped in a dict
            return {"type": "raw_text", "data": [text]} 
            
        elif "footer" in zone_type.lower():
            # Scenario B: Footer Extraction
            prompt = f"""
            Target Zone: {description}
            
            Task: Extract global financial fields from the summary/footer block.
            
            Fields to Extract:
            - **sub_total**: The total of all line items BEFORE tax and discount.
            - **global_discount**: Total discount applied at the bottom. NOTE: If you see "Disc %" with a large decimal value (e.g. 215.03), it is an AMOUNT, not a percentage. Extract it. Ignore leading minus signs.
            - **taxable_value**: Sub-total minus global_discount.
            - **total_sgst**: Total SGST amount.
            - **total_cgst**: Total CGST amount.
            - **round_off**: Rounding adjustment.
            - **Stated_Grand_Total**: The final 'Net Payable' amount.
            
            CRITICAL:
            - The 'Stated_Grand_Total' is the absolute anchor.
            - If you see "Taxable Value" in the footer, map it to 'taxable_value'.
            
            Return JSON:
            {{
                "sub_total": float,
                "global_discount": float,
                "taxable_value": float,
                "total_sgst": float,
                "total_cgst": float,
                "round_off": float,
                "Stated_Grand_Total": float
            }}
            """
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt, image_file]
            )
            text = response.text.strip()
            
            # Robust JSON Extraction
            import re
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                clean_json = json_match.group(0)
                data = json.loads(clean_json)
                return {"type": "modifiers", "data": data}
            else:
                    # Fallback: Try raw load or return empty
                    try:
                        data = json.loads(text)
                        return {"type": "modifiers", "data": data}
                    except:
                        return {"type": "error", "error": f"Invalid JSON from Header: {text[:50]}..."}
            
        elif "header" in zone_type.lower():
            # Scenario C: Header Extraction
            prompt = f"""
            Target Zone: {description}
            
            Task: Extract invoice header details.
            
            视觉区═══════════════════════════════════════════════════════
            CRITICAL DISTINCTION — SELLER vs BUYER:
            ═══════════════════════════════════════════════════════════
            This invoice has TWO parties. You must extract the SELLER only.
            
            SELLER (extract this):
            - The company ISSUING the invoice.
            - Found near labels: "Registered Name", "From:", "Firm Name", or at the top-left header.
            - Has a GSTIN/DL No associated with it.
            
            BUYER (DO NOT extract this as Supplier_Name):
            - Found near labels: "Customer Name", "Bill To", "Party:", "Consignee".
            - **If you see "Customer Name: Ram Chand and Sons", do NOT return "Ram Chand and Sons" as Supplier_Name.**
            - The Buyer does NOT have the invoice's GSTIN.
            ═══════════════════════════════════════════════════════════
            
            Fields:
            - Supplier_Name: The SELLER's company name (NOT the Customer Name).
            - Invoice_No
            - Invoice_Date (YYYY-MM-DD format preferred)
            
            NEGATIVE CONSTRAINTS:
            - IGNORE "Bank Details"
            - IGNORE "Outstanding"
            - NEVER return the value next to "Customer Name:" or "Bill To:" as Supplier_Name.
            
            CRITICAL INSTRUCTION:
            - RETURN ONLY VALID JSON.
            - NO CONVERSATIONAL TEXT. NO "Here is the JSON".
            - IF DATA IS MISSING, RETURN NULL/NONE.
            
            Return JSON:
            {{
                "Supplier_Name": "string",
                "Invoice_No": "string",
                "Invoice_Date": "string"
            }}
            """
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt, image_file]
            )
            text = response.text.strip()
            
            # Robust JSON Extraction
            import re
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                clean_json = json_match.group(0)
                data = json.loads(clean_json)
                return {"type": "modifiers", "data": data}
            else:
                    # Fallback: Try raw load or return empty
                    try:
                        data = json.loads(text)
                        return {"type": "modifiers", "data": data}
                    except:
                        return {"type": "error", "error": f"Invalid JSON from Header: {text[:50]}..."}
        
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

    # Prepare Image
    try:
        logger.info("Worker: Preprocessing image (Perspective Warp + Binarization)...")
        processed_bytes = preprocess_image_for_ocr(image_path)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(processed_bytes)
            tmp_image_path = tmp_file.name
            
        logger.info(f"Worker: Processed image saved to {tmp_image_path}")
        
    except Exception as e:
        logger.error(f"Worker warning: Preprocessing failed ({e}). Using original image.")
        tmp_image_path = image_path

    try:
        # Upload the PROCESSED image via manager (throttled)
        sample_file = await manager.upload_file_async(file_path=tmp_image_path)
        
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
            {feedback_context}
            
            TASK: EXTRACT ALL TABLES AS RAW MARKDOWN.
            
            Instructions:
            1. Find the main table with Products, Qty, Amounts.
            2. Convert it VISUALLY into a Pipe-Separated Markdown table.
            3. **Do not merge rows**. Keep every single line item separate.
            4. **AMOUNT RULE**: Extract the PRE-TAX, PRE-DISCOUNT "Amount" for each line.
            5. **FOOTER**: Extract sub_total, global_discount, total_sgst, total_cgst, and round_off from the bottom summary.
            6. **DUPLICATES**: If the Exact Same Item appears multiple times, LIST IT MULTIPLE TIMES.
            7. Capture exact headers like "Pcode", "Rate", "Amount", "Total".
            
            NEGATIVE CONSTRAINTS (CRITICAL):
            - **IGNORE "Initiative Name" Tables**: Do NOT extract tables with headers like "Initiative Name", "Product Batch No", "Free Product". These are schemes, not line items.
            - **IGNORE "Tax" Breakdowns**: Do not extract GST summary tables.
            - **IGNORE "Bank Details"**: Do not extract bank info as rows.
            
            Output Header (if first try): sub_total, global_discount, taxable_value, total_sgst, total_cgst, round_off, Stated_Grand_Total.
            
            Output ONLY the table.
            """
            
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=[prompt, sample_file]
            )
            text = response.text.strip()
            
            raw_text_rows = [text] 
            line_item_fragments = []
            error_logs = []
            
        else:
            # NORMAL MODE: ZONE BASED
            tasks = []
            for zone in plan:
                tasks.append(extract_from_zone(None, sample_file, zone))
                
            # Run Concurrent
            results = await asyncio.gather(*tasks)
            
            # Aggregate Results
            line_item_fragments = [] 
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
                
        # Increment Strategy: Just return 1, the state reducer (operator.add) handles the accumulation.
        current_total_retries = int(state.get("retry_count", 0))
        new_total = current_total_retries + 1
        
        # Calculate effective count for logging
        effective_count = len(line_item_fragments) if line_item_fragments else len(raw_text_rows)
        logger.info(f"Worker: Extraction Complete. Attempt {new_total}. Items Found: {effective_count} (Raw Fragments: {len(raw_text_rows)})")

        if retry_count > 0:
            return {
                "raw_text_rows": raw_text_rows,
                "error_logs": error_logs,
                "retry_count": 1
            }

        return {
            "line_item_fragments": [], 
            "raw_text_rows": raw_text_rows,
            "global_modifiers": global_modifiers,
            "anchor_totals": anchor_totals,
            "error_logs": error_logs,
            "retry_count": 1
        }
        
    except Exception as e:
        logger.error(f"Worker Master Error: {e}")
        return {
            "error_logs": [f"Worker Execution Failed: {str(e)}"],
            "retry_count": 1
        }
