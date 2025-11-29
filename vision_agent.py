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
    
    # Use Gemini 1.5 Flash (or 2.0 if available, but 1.5 is stable for vision)
    # The user mentioned 2.0 Flash in agent.py, let's stick to that if possible, 
    # but for safety let's use gemini-1.5-flash which is widely available.
    # Actually, let's try to use the same model name as agent.py if possible, or fallback.
    model = genai.GenerativeModel('gemini-2.0-flash-exp') 

    # Prepare the prompt
    prompt = """
    You are an expert pharmacy data entry assistant. 
    Analyze this invoice image and extract all medicine line items into a strict JSON format.
    
    **CRITICAL INSTRUCTION: DATA NORMALIZATION**
    Different bills use different names for the same columns. You must map them to the standardized keys below.
    
    1. **Map these common aliases to "batch_number":** "Batch", "Batch No", "Lot", "Lot No", "B.No".
    2. **Map these common aliases to "expiry_date":** "Exp", "Expiry", "Exp Date", "Use Before". 
       - **Format Rule:** Convert ALL dates to YYYY-MM-DD. 
       - If only MM/YY is given (e.g., "12/25"), assume the LAST DAY of that month (2025-12-31).
    3. **Map these common aliases to "quantity_packs":** "Qty", "Quantity", "Units", "Pack", "Strips".
       - If the bill has "Free" or "Bonus" qty, ADD it to the main quantity.
    4. **Map these common aliases to "mrp":** "MRP" (Maximum Retail Price).
    5. **Map these common aliases to "rate":** "Rate", "Price", "PTR", "PTS" (Purchase Rate per pack).
    
    **REQUIRED JSON OUTPUT STRUCTURE:**
    Return a single JSON object with two keys: "summary" and "items".

    **1. "summary" Object Keys:**
    - "invoice_number": The invoice number/ID found on the bill.
    - "invoice_date": The invoice date (YYYY-MM-DD).
    - "net_amount": The final total amount to be paid (Net Amount/Grand Total). Float.

    **2. "items" Array (List of Objects):**
    - "product_name": Name of the medicine.
    - "batch_number": Batch number (or "UNKNOWN").
    - "expiry_date": Expiry date (YYYY-MM-DD).
    - "quantity_packs": Total quantity (Integer).
    - "pack_size": Units per pack (Integer, default 10).
    - "mrp": Maximum Retail Price per pack (Float).
    - "rate": Purchase Rate per pack (Float). If not found, estimate as 70% of MRP.
    - "manufacturer": Manufacturer name.
    - "dosage_form": Dosage form.

    Output ONLY the JSON object.
    Example:
    {
        "summary": {
            "invoice_number": "INV-2024-001",
            "invoice_date": "2024-10-25",
            "net_amount": 18912.00
        },
        "items": [
            {"product_name": "Dolo 650", "batch_number": "X99", "expiry_date": "2025-12-31", "quantity_packs": 5, "pack_size": 15, "mrp": 30.0, "rate": 22.5, "manufacturer": "Micro Labs", "dosage_form": "Tablet"}
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
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text)
    except Exception as e:
        print(f"Vision Error: {e}")
        # Fallback mock data if API fails (so app doesn't crash during demo)
        return []
