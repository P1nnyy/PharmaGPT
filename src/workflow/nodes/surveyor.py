from google import genai
import os
import json
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.utils.ai_retry import ai_retry

# Setup Logging
logger = get_logger("surveyor")

# Initialize Gemini Client
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

client = genai.Client(api_key=API_KEY) if API_KEY else None

from langfuse import observe

@ai_retry
@observe(name="surveyor_layout_analysis")
def survey_document(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Layout Discovery Node.
    Analyzes the document image to identify distinct zones (tables, footers).
    Returns an update to the state with 'extraction_plan'.
    """
    image_path = state.get("image_path")
    if not image_path or not os.path.exists(image_path):
        logger.error(f"Image not found at {image_path}")
        return {"extraction_plan": [], "error_logs": [f"Image not found: {image_path}"]}

    try:
        # Validate Image
        if os.path.getsize(image_path) == 0:
            logger.error(f"Image is empty: {image_path}")
            return {"extraction_plan": [], "error_logs": ["Image file is empty"]}

        # Upload file with Retries
        sample_file = None
        upload_retries = 3
        for attempt in range(upload_retries):
            try:
                # In the new SDK, upload is via client.files.upload
                sample_file = client.files.upload(path=image_path)
                logger.info(f"File uploaded successfully: {sample_file.name}")
                break
            except Exception as e:
                logger.warning(f"Upload Attempt {attempt+1} failed: {e}")
                import time
                time.sleep(2) # Wait before retry
                if attempt == upload_retries - 1:
                     return {"extraction_plan": [], "error_logs": [f"Surveyor Upload Failed: {str(e)}"]}
        
        prompt = """
        Analyze this invoice and identify distinct layout zones.
        
        CRITICAL GOAL: Distinguish the "Main Product Line Item Table" from "Tax/HSN Summaries".
        
        42. Primary Table (Product List):
           - **MUST CONTAIN** a column for 'Description', 'Item Name', 'Product', or 'Particulars'.
           - It usually spans the middle of the document.
           - Label this zone_type: "primary_table".
           - **DISTINCTION**: If a table has "HSN" and "Tax" columns but **LACKS** a "Description/Item Name" column, it is a TAX SUMMARY. Ignore it.
           - Use zone_id: "table_1".

        2. Secondary Tables (IGNORE THESE AS PRIMARY):
           - **Tax Summary / HSN Summary**: Often at the bottom, contains 'Taxable Amt', 'CGST', 'SGST', 'Total Tax'. **DO NOT** claim this as the primary table.
           - **Schemes / Free Goods**: Small detached tables.

        3. Header: Top section with Supplier Name, Invoice Date, Invoice No.
        4. Footer: Bottom section with Grand Total, Net Payable, Bank Details.
        
        Output JSON Schema: 
        [
            {
                "zone_id": "header_1",
                "type": "header",
                "description": "Top section with supplier details"
            },
            {
                "zone_id": "table_1", 
                "type": "primary_table", 
                "description": "Main product grid with columns Item, Qty, Rate, Amount"
            },
            {
                "zone_id": "footer_1",
                "type": "footer",
                "description": "Footer area with Grand Total and Tax Breakdown"
            }
        ]
        """

        # Generate content with the new SDK
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, sample_file]
        )
        response_text = response.text
        
        # Clean Code Blocks
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        extraction_plan = json.loads(clean_json)
        
        logger.info(f"Surveyor Plan: {len(extraction_plan)} zones identified.")
        return {"extraction_plan": extraction_plan}

    except Exception as e:
        logger.error(f"Surveyor failed after retries: {e}")
        return {"extraction_plan": [], "error_logs": [f"Surveyor Error: {str(e)}"]}
