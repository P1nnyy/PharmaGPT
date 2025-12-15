import google.generativeai as genai
import os
import json
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

# Setup Logging
logger = get_logger("surveyor")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

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
        model = genai.GenerativeModel('gemini-2.0-flash') # Using 2.0 Flash as requested
        
        # Upload file (or load bytes if standard API supports it, but File API is better for vision)
        # Using standard file API for Gemini 2.0
        sample_file = genai.upload_file(path=image_path, display_name="Invoice Surveyor")
        
        prompt = """
        Analyze this invoice and identify distinct layout zones.
        
        CRITICAL GOAL: Distinguish the "Main Product Line Item Table" from "Tax/HSN Summaries".
        
        1. Primary Table (Product List):
           - Look for a large grid containing 'Description', 'Qty', 'Rate', 'Amount', 'Batch'.
           - It usually spans the middle of the document.
           - Label this zone_type: "primary_table".
           - Use zone_id: "table_1".

        2. Secondary Tables (IGNORE THESE AS PRIMARY):
           - **Tax Summary / HSN Summary**: Often at the bottom, contains 'Taxable Amt', 'CGST', 'SGST', 'Total Tax'. **DO NOT** claim this as the primary table.
           - **Schemes / Free Goods**: Small detached tables.
           - Label these zone_type: "secondary_table".

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

        response = model.generate_content([prompt, sample_file])
        response_text = response.text
        
        # Clean Code Blocks
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        extraction_plan = json.loads(clean_json)
        
        logger.info(f"Surveyor Plan: {len(extraction_plan)} zones identified.")
        
        return {"extraction_plan": extraction_plan}

    except Exception as e:
        logger.error(f"Surveyor failed: {e}")
        return {"extraction_plan": [], "error_logs": [f"Surveyor Error: {str(e)}"]}
