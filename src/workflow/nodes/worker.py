from src.services.ai_client import manager
import asyncio
import json
import os
import logging
import re
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.config_loader import load_column_aliases, load_vendor_rules
from src.utils.logging_config import get_logger
from src.utils.image_processing import preprocess_image_for_ocr
from src.utils.ai_retry import ai_retry
import tempfile

logger = get_logger(__name__)

WORKER_SEMAPHORE = asyncio.Semaphore(2)

def get_config_context() -> str:
    """
    Loads column aliases and vendor rules into a formatted string for the LLM.
    """
    try:
        aliases = load_column_aliases().get("global_column_aliases", {})
        vendor_data = load_vendor_rules().get("vendors", {})
        
        alias_context = "\n".join([f"- **{k}**: {', '.join(v)}" for k, v in aliases.items()])
        
        vendor_context = ""
        for vendor, details in vendor_data.items():
            if details.get("aliases") or details.get("extraction_notes"):
                vendor_context += f"\nVendor: {vendor}\n"
                if details.get("aliases"):
                    vendor_context += f"  Aliases: {json.dumps(details.get('aliases'))}\n"
                if details.get("extraction_notes"):
                    notes = details.get("extraction_notes").replace('\n', ' ')
                    vendor_context += f"  Notes: {notes}\n"

        config_str = f"""
        [GLOBAL COLUMN ALIASES]
        {alias_context}
        
        [VENDOR SPECIFIC RULES]
        {vendor_context}
        
        [STRICT OVERRIDE INSTRUCTION]
        Use your general reasoning to extract the invoice data. However, you MUST treat the provided column_aliases and vendor_rules as high-priority overrides. If you encounter an ambiguous column, check the aliases. If the supplier matches a vendor in the rules (like C M Associates), you must rigidly apply their specific mappings (e.g., mapping PCode to Batch_No as defined).
        """
        return config_str
    except Exception as e:
        logger.error(f"Failed to load config context for LLM: {e}")
        return ""

@ai_retry
async def execute_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Worker Node.
    Executes the extraction plan concurrently using a batch-consolidated prompt architecture.
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
        # Check Retry State
        retry_count = int(state.get("retry_count", 0))
        cached_name = state.get("cached_content_name")
        feedback_logs = state.get("feedback_logs", [])
        feedback_context = ""
        
        sample_file = None
        
        if retry_count > 0 and cached_name:
            logger.info(f"Worker: Using Gemini Context Cache: {cached_name}")
        else:
            sample_file = await manager.upload_file_async(file_path=tmp_image_path)
            
            logger.info("Worker: Creating Context Cache for future retry loops...")
            cached_content = await manager.create_cached_content_async(
                model='gemini-2.0-flash', 
                contents=[sample_file], 
                ttl_seconds=900
            )
            if cached_content:
                cached_name = cached_content.name

        if retry_count > 0 and feedback_logs:
            latest_feedback = feedback_logs[-1]
            feedback_context = f"\nPREVIOUS ATTEMPT FAILED. CRITIC FEEDBACK: {latest_feedback}\nPLEASE CORRECT THIS ERROR ENTIRELY."

        config_context = get_config_context()
        
        prompt = f"""
        You are a MASTER INVOICE DATA EXTRACTOR.
        Analyze the entire document image.
        
        **CONFIGURATION & RULES:**
        {config_context}
        
        {feedback_context}
        
        TASK: EXTRACT ALL RELEVANT DATA FROM THIS INVOICE IMAGE DIRECTLY INTO STRUCTURED JSON.
        
        The surveyor evaluated the layout of this document with the following bounding plan:
        {json.dumps(plan, indent=2)}
        Make sure to parse these primary zones accordingly. 
        
        SELLER VS BUYER (CRITICAL):
        - Supplier_Name must be the SELLER ISSUING the invoice.
        - NEVER output the Buyer/Customer ("Bill To", "Party") as the Supplier_Name!
        
        TABLE EXTRACTION RULES:
        - **Split Qty + Free**: If you see "10+2" in a Quantity column, Qty=10, Free=2.
        - **Prices vs Qty**: "MRP" and "Rate" are typically > 10. "Qty" is typically small.
        - **Ignore UFC/Pack as Price**: If you see "Pack", "Unit", "UFC", do not map it to MRP or Rate.
        - **Merge Control**: Do NOT merge duplicate lines. If "Dolo 650" appears twice in the image, output two distinct JSON items.
        - **Splits**: If "Batch No" is embedded inside the Description cell, split it out.
        - **Returns**: If a row is clearly a 'Sales Return' or 'Credit Note', output negative Qty, negative Amount.
        
        FOOTER / FINANCIAL RULES:
        - **sub_total**: Total of all line items BEFORE tax & discount.
        - **Stated_Grand_Total**: Final payable amount at the bottom.
        - **credit_note_amount**: Standalone return deductions in the summary.
        - **Tax amounts**: total_sgst, total_cgst.
        
        RETURN ONLY A VALID JSON STRUCTURE WITH THE EXACT FOLLOWING SCHEMA (If missing, use null or 0.0):
        {{
            "Supplier_Name": "string",
            "Invoice_No": "string",
            "Invoice_Date": "string",
            "sub_total": 0.0,
            "global_discount": 0.0,
            "taxable_value": 0.0,
            "total_sgst": 0.0,
            "total_cgst": 0.0,
            "credit_note_amount": 0.0,
            "extra_charges": 0.0,
            "round_off": 0.0,
            "Stated_Grand_Total": 0.0,
            "supplier_details": {{
                "gstin": "string",
                "phone": "string",
                "address": "string",
                "dl_no": "string"
            }},
            "line_items": [
                {{
                    "Product": "string",
                    "Pack": "string",
                    "Qty": 0.0,
                    "Free": 0.0,
                    "Batch": "string",
                    "Expiry": "string",
                    "HSN": "string",
                    "MRP": 0.0,
                    "Rate": 0.0,
                    "Amount": 0.0,
                    "Manufacturer": "string",
                    "Raw_GST_Percentage": 0.0
                }}
            ]
        }}
        """

        async with WORKER_SEMAPHORE:
            from google.genai import types
            
            input_contents = [prompt]
            if sample_file:
                input_contents.append(sample_file)
                
            gen_config = {}
            if cached_name and retry_count > 0:
                gen_config["cached_content"] = cached_name
                input_contents = [prompt] # Pass prompt only if using Cache to avoid duplication 
            
            response = await manager.generate_content_async(
                model='gemini-2.0-flash',
                contents=input_contents,
                config=types.GenerateContentConfig(**gen_config) if gen_config else None
            )
            
        text = response.text.replace("```json", "").replace("```", "").strip()
        
        # Fallback to Regex extraction if preamble exists
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
            
        data = json.loads(text)
        
        # Aggregation Structure for State Reducer
        line_item_fragments = data.get("line_items", [])
        
        global_modifiers = {
            "Supplier_Name": data.get("Supplier_Name"),
            "Invoice_No": data.get("Invoice_No"),
            "Invoice_Date": data.get("Invoice_Date"),
            "sub_total": data.get("sub_total"),
            "global_discount": data.get("global_discount"),
            "taxable_value": data.get("taxable_value"),
            "total_sgst": data.get("total_sgst"),
            "total_cgst": data.get("total_cgst"),
            "credit_note_amount": data.get("credit_note_amount"),
            "extra_charges": data.get("extra_charges"),
            "round_off": data.get("round_off"),
            "Stated_Grand_Total": data.get("Stated_Grand_Total"),
            "supplier_details": data.get("supplier_details", {})
        }
        
        anchor_totals = {}
        if "Stated_Grand_Total" in global_modifiers and global_modifiers["Stated_Grand_Total"]:
            try:
                anchor_totals["Stated_Grand_Total"] = float(global_modifiers["Stated_Grand_Total"])
            except Exception:
                pass

        current_total_retries = int(state.get("retry_count", 0))
        new_total = current_total_retries + 1
        
        logger.info(f"Worker (Batch Optimized): Extraction Complete. Attempt {new_total}. Items Found: {len(line_item_fragments)}")

        if retry_count > 0:
            return {
                "line_item_fragments": line_item_fragments,
                "global_modifiers": global_modifiers,
                "anchor_totals": anchor_totals,
                "error_logs": [],
                "retry_count": 1, # Resolves via operator.add
                "cached_content_name": cached_name
            }

        return {
            "line_item_fragments": line_item_fragments, 
            "raw_text_rows": [], # Deprecated
            "global_modifiers": global_modifiers,
            "anchor_totals": anchor_totals,
            "error_logs": [],
            "retry_count": 1,
            "cached_content_name": cached_name
        }
        
    except Exception as e:
        logger.error(f"Worker Master Error: {e}")
        return {
            "error_logs": [f"Worker Execution Failed: {str(e)}"],
            "retry_count": 1
        }
