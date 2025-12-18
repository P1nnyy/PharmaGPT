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
    
    # Load Memory
    from src.services.mistake_memory import MEMORY
    rules = MEMORY.get_rules()
    memory_rules = "\n    ".join([f"- {r}" for r in rules]) if rules else "- No previous mistakes recorded."
    
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
    - **Pack**: Pack Size if visible (e.g. "1x10", "10's", "10T").
    - **Qty**: Numeric (Float). Billed Quantity.
      - **Aliases**: Look for "Billed", "Sales Qty", "Strips", "Tabs", "Packs", "Quantity".
      - **Split**: If column is "10+2", use 10.
      - **Multi-Column**: If text is "0 0 2" or "0 2", extract the NON-ZERO number (e.g. 2).
      - **Fractional**: If you see "1.84" or "0.92", ROUND IT to the nearest integer/whole pack (e.g. 1.84 -> 2, 0.92 -> 1).
    - **Batch**: Alphanumeric Batch Number. 
      - **Look for aliases**: "Pcode", "Code", "Lot". 
      - **Extraction**: If a column has "Pcode: 808..." extract that as Batch.
    - **Expiry**: Text date (MM/YY or DD/MM/YY).
      - **CRITICAL**: Do NOT put a 4-8 digit HSN code (e.g. 3004, 30049099) here.
      - If you see an integer like "3004" or "30043110", put it in HSN, NOT Expiry.
    - **HSN**: Numeric HSN code (4-8 digits).
    - **Rate**: Unit Price.
    - **Rate**: Unit Price.
      - **CRITICAL**: Watch for faint decimal points. "16000" is likely "160.00".
      - "12345" is likely "123.45".
    - **Amount**: Net Total (Inclusive of Tax).
      - **CRITICAL**: Watch for faint decimal points.
      - **Consistency**: Ideally `Qty * Rate` ~= `Amount`. If `Amount` is wildly different, check if you missed a decimal in Rate or Amount.
      - **Selection**: If "Total" and "Amount" both exist, prefer "Amount" (usually strict final). Avoid "Total" if it looks like Gross/MRP-based.
    - **MRP**: Max Retail Price.
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products. "Vaporub 5gm" and "Vaporub 10gm" are DIFFERENT.
    2. **DUPLICATES**: If the raw text lists the SAME product twice (e.g. "Dolo 650" appears on two lines), CREATE TWO JSON OBJECTS. Do NOT merge them into one. Keep them separate.
    3. **Noise**: Ignore header rows (e.g. "Description | Qty").
    4. **Schemes**: Keep "Offer" / "Free" rows if they are separate line items.
    
    SYSTEM MEMORY (PREVIOUS MISTAKES TO AVOID):
    {memory_rules}
    
    Output JSON format:
    {{
        "line_items": [
            {{
                "Product": "str",
                "Pack": "str",
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
