import google.generativeai as genai
import json
import os
import logging
from typing import Dict, Any
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
import re

logger = get_logger(__name__)

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

async def extract_header_metadata(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Specialized Agent to extract rich supplier metadata and invoice headers.
    Ignores the table grid to focus on top/bottom details.
    """
    image_path = state.get("image_path")
    if not image_path:
        return {"error_logs": ["HeaderAgent: Missing image path."]}

    try:
        # Prepare Model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Upload File (Directly use path if supported, or rely on worker's preprocessing if shared. 
        # For independence, we upload here. Gemini handles duplicates well via hash)
        sample_file = genai.upload_file(path=image_path, display_name="Header Extraction")
        
        prompt = """
        TASK: EXTRACT SUPPLIER METADATA & INVOICE HEADERS
        
        Target Zones: Header (Top 20%) and Footer (Bottom 20%).
        IGNORE: The central line item table.
        
        GOAL: We need to capture contact details so we can contact the supplier later.
        
        Fields to Extract:
        1. **Supplier_Name**: The main business name at the top (e.g., "KUMAR BROTHERS PHARMACEUTICALS").
        2. **Address**: The full text address. One line preferred.
        3. **Phone_Primary**: Look for "Mob", "Ph", "Call", or just 10-digit numbers. High Priority.
        4. **Phone_Secondary**: If a second number exists (landline or alternate mobile).
        5. **Email**: Look for "@".
        6. **GSTIN**: 15-character alphanumeric (e.g., "03AAGFK...").
        7. **Drug_License_20B**: Look for "D.L.", "License", "20B". Format often "20B-..." or just numbers near "20B".
        8. **Drug_License_21B**: Look for "21B".
        9. **Invoice_No**: The main invoice identifier.
        10. **Invoice_Date**: Date of the invoice (YYYY-MM-DD format preferred).
        
        CRITICAL RULES:
        - **Phone Numbers**: Remove spaces/dashes. e.g., "94173 13201" -> "9417313201".
        - **DL Handling**: If "20B/21B" are listed together (e.g. "20B/21B-12345"), assign "12345" to BOTH 20B and 21B fields.
        
        OUTPUT FORMAT (JSON ONLY):
        {
            "Supplier_Name": "string",
            "Address": "string",
            "Phone_Primary": "string",
            "Phone_Secondary": "string",
            "Email": "string",
            "GSTIN": "string",
            "Drug_License_20B": "string",
            "Drug_License_21B": "string",
            "Invoice_No": "string",
            "Invoice_Date": "string"
        }
        """
        
        logger.info("HeaderAgent: Analyzing image for metadata...")
        response = await model.generate_content_async([prompt, sample_file])
        text = response.text.strip()
        
        # Robust JSON Extraction
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
            data = json.loads(clean_json)
            
            # Sanitize None keys to avoid Pydantic issues if passed raw
            cleaned_data = {k: v for k, v in data.items() if v is not None}
            
            logger.info(f"HeaderAgent: Success. Extracted {cleaned_data.get('Supplier_Name', 'Unknown')}")
            return {"header_data": cleaned_data}
        else:
            logger.warning(f"HeaderAgent: Failed to parse JSON. Response: {text[:100]}...")
            return {"header_data": {}}
            
    except Exception as e:
        logger.error(f"HeaderAgent Error: {e}")
        return {"error_logs": [f"HeaderAgent Failed: {str(e)}"], "header_data": {}}
