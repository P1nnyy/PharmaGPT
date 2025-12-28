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
    
    # Load Memory (Learning System)
    try:
        from src.services.mistake_memory import MEMORY
        rules = MEMORY.get_rules()
        if rules:
             memory_rules = "\n    ".join([f"- {r}" for r in rules])
        else:
             memory_rules = "- No previous mistakes recorded."
    except Exception as e:
        logger.warning(f"Mapper Memory Load Failed: {e}")
        memory_rules = "- Memory System Unavailable."
    
    # Feedback from previous attempts (Immediate Correction)
    current_feedback = state.get("feedback_logs", [])
    feedback_text = ""
    if current_feedback:
        feedback_text = "\n    CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT:\n    " + "\n    ".join(current_feedback)

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
    - **Section**: "Main" or "Sales Return". 
      - **Rule**: If you see a row saying "SALES RETURN", "RETURN GROSS", or "CREDIT NOTE", then ALL subsequent items belong to `Section: "Sales Return"`.
    - **Product**: Full description.
    - **is_sales_return**: (Boolean). Set to true IF the item appears under a "SALES RETURN" header or section. (Legacy: Prefer Section).
    - **Pack**: Pack Size if visible (e.g. "1x10", "10's", "10T").
    - **Qty**: Numeric (Float). Total Quantity (Billed + Free).
      - **Aliases**: Look for "Billed", "Sales Qty", "Strips", "Tabs", "Packs", "Quantity".
      - **Combined format**: If text is "10+2", SUM THEM (e.g. 12).
      - **Separate Columns**: If you see separate "Qty" (10) and "Free" (2) columns, ADD THEM (12).
      - **Fractional**: PRESERVE decimals (e.g. 1.5).
      - **Multi-Column Conflict**: If text is "0 0 2", use 2.
    - **Batch**: Alphanumeric Batch Number. 
      - **Look for aliases**: "Pcode", "Code", "Lot". 
      - **Extraction**: If a column has "Pcode: 808..." extract that as Batch.
    - **Expiry**: Text date (MM/YY or DD/MM/YY).
      - **CRITICAL**: Do NOT put a 4-8 digit HSN code (e.g. 3004, 30049099) here.
    - **HSN**: Numeric HSN code (4-8 digits).
    - **Rate**: Unit Price (PTS/PTR).
      - **CRITICAL**: Watch for faint decimal points. "16000" is likely "160.00".
    - **Amount**: Net Total (Inclusive of Tax).
      - **Selection**: If "Total" and "Amount" both exist, prefer "Amount".
    - **MRP**: Max Retail Price (PER UNIT).
      - **CRITICAL**: Do NOT extract the "Amount" or "Net Total" column as MRP.
      - **CRITICAL**: Do NOT extract HSN Code (e.g. 3004, 1080) as MRP.
      - **Rule**: MRP is usually > Rate. If you see a Rate of 100, MRP cannot be 5.
      - **Formatting**: Watch for faint decimals (e.g. 1080 -> 10.80).
    
    CRITICAL:
    1. **Merges**: DO NOT merge distinct products. "Vaporub 5gm" and "Vaporub 10gm" are DIFFERENT.
    2. **DUPLICATES**: If the raw text lists the SAME product twice (e.g. "Dolo 650" appears on two lines), CREATE TWO JSON OBJECTS. Do NOT merge them into one. Keep them separate.
    3. **"TOTAL" Confusion**: The word "TOTAL" may appear in a product name (e.g. "REVITAL TOTAL"). DO NOT treat this as the end of the invoice. Only stop if you see a footer like "Grand Total" with a large monetary value.
    4. **Completeness**: If the rows are numbered (e.g., 1 to 18), ensure ALL rows (1 to 18) are present in the JSON. If row 18 is "BEMINAL TOTAL...", INCLUDE IT.
    5. **SALES RETURN**: Check for a row/header saying "SALES RETURN". Items listed AFTER/BELOW this header are returned items. Mark them as `"is_sales_return": true`. Do NOT ignore them, but flag them.
    6. **Noise**: Ignore header rows (e.g. "Description | Qty").
    7. **Schemes**: Keep "Offer" / "Free" rows if they are separate line items.
    
    {feedback_text}
    
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
