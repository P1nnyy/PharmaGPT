import google.generativeai as genai
import json
import os
from typing import Dict, Any, Optional
from src.utils.logging_config import get_logger

logger = get_logger("contact_hunter")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

async def extract_supplier_details(image_path: str) -> Dict[str, Optional[str]]:
    """
    Extracts supplier contact details (Phone, GST) from the invoice image.
    Run this in parallel with the main pipeline to avoid blocking.
    """
    if not image_path or not os.path.exists(image_path):
        logger.warning(f"Contact Hunter: Image not found at {image_path}")
        return {}

    logger.info("Contact Hunter: Scanning for Supplier Phone & GST...")

    try:
        sample_file = genai.upload_file(image_path, mime_type="image/jpeg")
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = """
        Analyze this invoice image and extract the Supplier's Contact Details.
        
        Look for:
        1. **Phone Number**: Look for labels like "Ph", "Mob", "Contact", "Cell". Return the number as a string. If multiple, return the first one.
        2. **GSTIN**: Look for "GSTIN", "GST", "TIN".
        
        Output JSON format only:
        {
            "Supplier_Phone": "string or null",
            "Supplier_GST": "string or null"
        }
        """

        response = await model.generate_content_async([sample_file, prompt])
        text = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        
        phone = result.get("Supplier_Phone")
        gst = result.get("Supplier_GST")
        
        # Cleanup
        if phone == "null": phone = None
        if gst == "null": gst = None

        logger.info(f"Contact Hunter: Found Phone={phone}, GST={gst}")
        
        return {
            "Supplier_Phone": phone,
            "Supplier_GST": gst
        }

    except Exception as e:
        logger.error(f"Contact Hunter Failed: {e}")
        return {}
