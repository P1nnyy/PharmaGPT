import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

class ScoutAgent:
    """
    Council of Agents: Scout (Step 1).
    Responsible for identifying the Supplier Name and the exact list of Column Headers
    from the main transaction table.
    """
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                'gemini-2.0-flash',
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0
                }
            )
        else:
            self.model = None

    def scan(self, image_path: str) -> Dict[str, Any]:
        """
        Scans the invoice to identify structure.
        Returns: {"supplier_name": str, "detected_headers": List[str]}
        """
        if not self.model:
            logger.warning("No API Key provided for ScoutAgent.")
            return {}

        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
                
            mime_type = "image/jpeg" 
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            prompt = """
            Analyze the invoice image and identify ALL distinct grid or table structures containing transaction line items.
            
            1. **Supplier Name**: The name of the vendor/supplier issuing the invoice.
            2. **Tables**: Identify all distinct tables containing product data.
               - **Primary Table**: The main list of goods/products.
               - **Secondary Tables**: Separate sections for Free Goods, Cold Chain items, Schedule H drugs, or other product listings.
            
            Return a JSON object strictly matching this schema:
            {
                "supplier_name": "string",
                "tables": [
                    {
                        "id": "string", # e.g., "primary_table", "cold_chain_table"
                        "type": "Primary", # or "Secondary"
                        "description": "string", # e.g., "Main Product List", "Free Goods Section"
                        "detected_headers": ["string", "string", ...]
                    }
                ]
            }
            
            INSTRUCTIONS:
            - **Identify ALL Tables**: Do not limit to just the largest one. Look for multiple separated grids.
            - **Header Extraction**: For each table, extract the exact list of column headers.
            - **Ignore Non-Product Grids**: Do not extract headers from Tax Breakdowns, HSN Summaries, or Dispatch Summaries.
            """
            
            response = self.model.generate_content(
                [
                    {"mime_type": mime_type, "data": image_data},
                    prompt
                ]
            )
            
            if response.text:
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    logger.error("Failed to parse ScoutAgent JSON output")
                    return {}
            
            return {}

        except Exception as e:
            logger.error(f"ScoutAgent Failed: {e}")
            return {}
