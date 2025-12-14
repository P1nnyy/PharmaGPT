import google.generativeai as genai
import asyncio
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
            vendor_context = "Learned Rules: None" # Placeholder for future injection

            prompt = f"""
            Target Zone: {description}
            Context: {vendor_context}
            
            Task: Extract line items from this specific section.
            
            CRITICAL RULES:
            1. **Batch Number Hunt**: You MUST find the Batch Number. Look for columns 'Batch', 'Lot', 'B.No'.
               - **CRITICAL EXCLUSION**: Do **NOT** extract values from columns labeled **"PCode"**, "Product Code", or "SKU". These are item codes, not batches.
               - **Fallback / Semantic Hunt**: If no specific Batch column exists, look for a "Batch Details" section elsewhere or a batch string (alphanumeric, e.g. 'B2G2', 'GT45') printed **inside** the Description column or near the 'Expiry' column. Do NOT return 'UNKNOWN' unless strictly empty.
            2. **Expiry Date Hunt**: Look for Expiry Dates (Exp, Expiry, Validity) in the row. Format as MM/YY or MM/YYYY if possible.
            3. **Single Pass Extraction**: Scan the table top-to-bottom exactly ONCE. Do NOT repeat items. Do NOT hallucinate double rows.
            4. **Blind Extraction**: Extract exactly what you see.
               - If a column looks like an Amount, extract it. 
               - Do NOT perform calculations. Do NOT attempt to multiply Qty * Rate.
               - Do NOT try to fix mismatches. Trust the printed text.
            5. **Tax Verification**: Strictly extract the tax rate as printed. If columns SGST(12%) and CGST(12%) exist, CHECK: do they sum to a standard rate (5, 12, 18, 28)?
            6. **Exclusions**: IGNORE 'Total', 'Subtotal', 'Discount', 'Freight' rows.
            7. **Output**: Return the raw values. The 'Stated_Net_Amount' should be the final column value for that row.
            
            Return a JSON object with a key 'line_items' containing a list of items.
            Item Schema:
            {{
                "Original_Product_Description": str,
                "Raw_Quantity": float,
                "Batch_No": str,
                "Raw_Expiry_Date": str,
                "Raw_HSN_Code": str,
                "Raw_Rate_Column_1": float,
                "Raw_Rate_Column_2": float,
                "Raw_MRP": float,
                "Raw_Discount_Percentage": float,
                "Raw_GST_Percentage": float,
                "Raw_Taxable_Value": float,
                "Stated_Net_Amount": float
            }}
            """
            response = await model.generate_content_async([prompt, image_file])
            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return {"type": "line_items", "data": data.get("line_items", [])}
            
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
    try:
        sample_file = genai.upload_file(path=image_path, display_name="Worker Extraction")
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Create Tasks
        tasks = []
        for zone in plan:
            tasks.append(extract_from_zone(model, sample_file, zone))
            
        # Run Concurrent
        results = await asyncio.gather(*tasks)
        
        # Aggregate Results
        line_item_fragments = []
        global_modifiers = {}
        anchor_totals = {}
        error_logs = []
        
        for res in results:
            if res.get("type") == "line_items":
                items = res.get("data", [])
                if isinstance(items, list):
                    line_item_fragments.extend(items)
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
                
        # Get current retry count and increment
        # This prevents infinite loops if Critic keeps rejecting
        current_retry = int(state.get("retry_count", 0))
        new_retry_count = current_retry + 1
        
        logger.info(f"Worker: Extraction Complete. Retry Count: {state.get('retry_count')} -> {new_retry_count}")

        return {
            "line_item_fragments": line_item_fragments,
            "global_modifiers": global_modifiers,
            "anchor_totals": anchor_totals,
            "error_logs": error_logs,
            "retry_count": new_retry_count
        }
        
    except Exception as e:
        logger.error(f"Worker Master Error: {e}")
        return {"error_logs": [f"Worker Execution Failed: {str(e)}"]}
