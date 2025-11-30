from datetime import datetime
import dateutil.parser

def normalize_date(date_str):
    """
    Tries to parse a date string and return it in YYYY-MM-DD format.
    Handles DD/MM/YY, MM/DD/YY, etc.
    """
    if not date_str:
        return None
    try:
        # Try parsing with dateutil (robust)
        # dayfirst=True is common for Indian bills (DD/MM/YY)
        dt = dateutil.parser.parse(date_str, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except:
        return None

import google.generativeai as genai
import os
import json
from PIL import Image
import io

def analyze_bill_image(image_bytes):
    """
    Analyzes a bill image using Gemini 2.0 Flash and extracts line items.
    Returns a list of dictionaries containing product details.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found.")
    
    genai.configure(api_key=api_key)
    
    # Use Gemini 2.0 Flash
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    # Prepare the prompt
    prompt = """
    You are 'Antigravity', an expert Pharmacy Invoice Extraction Agent.

    ### TASK: CHAIN-OF-THOUGHT EXTRACTION
    For each row in the invoice image, you must:
    1. **READ**: Transcribe the full text of the row from Left to Right.
    2. **EXTRACT**: Parse that text into the JSON structure.

    ### HEADER EXTRACTION (METADATA)
    Look at the top of the bill:
    1. **supplier_name**: The boldest text at the top (e.g., "DEEPAK AGENCIES").
    2. **invoice_number**: Label "Invoice No" or "Bill No".
    3. **invoice_date**: Label "Date" (YYYY-MM-DD).

    ### CRITICAL: COLUMN MAPPING & FALLBACKS
    - **Batch Number**: 
      - Look for a column named "Batch", "Batch No", "Lot".
      - **IMPORTANT**: If NO Batch column exists, look for "PCode", "Product Code", or "Code" and use THAT as the `batch_number`.
    
    - **Pack / Pack Size**:
      - Look for a column named "Pack", "Pkg", "Size".
      - **IMPORTANT**: If the Pack column is missing or empty, **EXTRACT** the pack size directly from the `product_name` or `description`.
      - Examples: "Vaporub 5gm" -> Pack="5gm", "Babyrub 10ml" -> Pack="10ml", "Dolo 650 15T" -> Pack="15T".

    - **Qty**: The FIRST or SECOND number on the far left. (e.g. "2", "10").
    - **Product**: The main text description.
    - **Expiry**: Look for dates like "05/27", "01/01/2027".

    ### RULES
    - **NEVER** guess "1x10" if no evidence exists.
    - **NEVER** guess `quantity`. If missing, return `null`.
    - **Expiry Date**: Convert to YYYY-MM-DD format if possible.

    ### OUTPUT JSON SCHEMA
    {
      "metadata": {
        "supplier_name": "string",
        "invoice_number": "string",
        "invoice_date": "string (YYYY-MM-DD)"
      },
      "items": [
        {
          "debug_raw_row_text": "string",
          "product_name": "string",
          "pack_label": "string",
          "pack_size": integer,
          "quantity": integer,
          "is_free": boolean,
          "mrp": float,
          "buy_price": float,
          "gst_rate": float,
          "batch_number": "string",
          "expiry_date": "string (YYYY-MM-DD)"
        }
      ]
    }
    """

    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        
        # Clean response
        text = response.text.strip()
        
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip() # Final strip
            
        data = json.loads(text)
        
        # --- POST-PROCESSING HEURISTICS ---
        if isinstance(data, dict) and "items" in data:
            for item in data["items"]:
                # 1. Mitigate "1x10" hallucinations
                name = item.get("product_name", "").upper()
                label = item.get("pack_label", "")
                non_tablet_keywords = ["CREAM", "GEL", "OINT", "SYRUP", "LIQUID", "SOL", "DROPS", "SPRAY", "POWDER", "SACHET", "GRANULES"]
                
                if label == "1x10" and any(k in name for k in non_tablet_keywords):
                    item["pack_label"] = "1"
                    item["pack_size"] = 1
                
                # 2. Default empty Pack Size to 1
                if not item.get("pack_label"):
                    item["pack_label"] = "1"
                    item["pack_size"] = 1

                # 3. Normalize Dates
                if item.get("expiry_date"):
                    item["expiry_date"] = normalize_date(item["expiry_date"])
                    
        return data
    except Exception as e:
        print(f"Vision Error: {e}")
        return []
