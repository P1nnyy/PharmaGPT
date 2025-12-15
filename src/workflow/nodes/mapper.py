import google.generativeai as genai
import json
import os
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("mapper")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

def execute_mapping(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Mapper Node.
    Stage 2 of Extraction.
    Takes Raw Text Rows (from Worker) and maps them to the Strict Schema.
    """
    raw_rows = state.get("raw_text_rows", [])
    
    if not raw_rows:
        logger.warning("Mapper: No raw text rows found. Skipping.")
        return {}

    logger.info(f"Mapper: Processing {len(raw_rows)} raw text fragments...")
    
    # Model Setup
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    # Construct Context from all rows
    # Each row is likely a string "Product | Qty | Rate"
    context_text = "\n".join(raw_rows)
    
    prompt = f"""
    You are a DATA STRUCTURE EXPERT.
    Your input is a raw, unstructured extraction from an invoice table (OCR Text).
    
    INPUT RAW TEXT:
    \"\"\"
    {context_text}
    \"\"\"
    
    YOUR TASK:
    Convert this text into a VALID JSON array of line items.
    
    SCHEMA RULES:
    - **Product**: Full description.
    - **Qty**: Numeric (Float). Billed Quantity. If "10+2", use 10.
    - **Batch**: Alphanumeric Batch Number. 
      - **Look for aliases**: "Pcode", "Code", "Lot". 
      - **Extraction**: If a column has "Pcode: 808..." extract that as Batch.
    - **Expiry**: Text date (MM/YY).
    - **HSN**: Numeric HSN code (4-8 digits).
    - **Rate**: Unit Price.
    - **Amount**: Net Total for the line.
    - **MRP**: Max Retail Price.
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products. "Vaporub 5gm" and "Vaporub 10gm" are DIFFERENT.
    2. **Noise**: Ignore header rows (e.g. "Description | Qty").
    3. **Schemes**: Keep "Offer" / "Free" rows if they are separate line items.
    
    Output JSON format:
    {{
        "line_items": [
            {{
                "Product": "str",
                "Qty": float,
                "Batch": "str",
                "Expiry": "str",
                "HSN": "str",
                "MRP": float,
                "Rate": float,
                "Amount": float
            }}
        ]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        mapped_items = data.get("line_items", [])
        logger.info(f"Mapper: Successfully mapped {len(mapped_items)} items.")
        
        return {"line_item_fragments": mapped_items}
        
    except Exception as e:
        logger.error(f"Mapper Error: {e}")
        return {"error_logs": [f"Mapper Failed: {e}"]}
