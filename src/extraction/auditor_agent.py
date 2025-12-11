import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, List
from src.utils.config_loader import load_product_catalog

logger = logging.getLogger(__name__)

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

class AuditorAgent:
    """
    Council of Agents: Auditor (Step 3).
    Responsible for text-to-text verification of the extracted JSON.
    Filters out financial rows and validates against known product anchors.
    """
    def __init__(self, api_key: str = API_KEY):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash',
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0
                }
            )
        else:
            self.model = None

    def audit(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits and cleans the extracted data.
        """
        if not self.model:
            logger.warning("No API Key provided for AuditorAgent.")
            return extracted_data

        try:
            # 1. Load Anchor Entities (Ground Truth)
            catalog = load_product_catalog()
            # Get top 10 known names to use as anchors
            anchor_names = [p.get("known_name") for p in catalog[:10]]
            anchor_str = ", ".join(f"'{n}'" for n in anchor_names)

            # 2. Prepare Data for Prompt
            input_json = json.dumps(extracted_data, indent=2)

            prompt = f"""
            You are an expert Invoice Auditor. 
            Review the following extracted invoice data (JSON) and perform a strict clean-up.

            INPUT DATA:
            {input_json}

            INSTRUCTIONS:
            1. **Remove Invalid Rows**: Remove any line item where the 'Original_Product_Description' contains text indicating it is NOT a product, such as:
               - "Output CGST", "Input CGST", "SGST", "IGST"
               - "Freight", "Round Off", "Total", "Grand Total", "Amount in Words"
               - Any row where 'Original_Product_Description' is empty or null.
               
            2. **Quantity Validation**: Verify that every remaining item has a valid 'Raw_Quantity' > 0. If Quantity is 0 or null, remove the row (unless it is a valid free item, but usually main items have qty).
            
            3. **Anchor Verification (Ground Truth Context)**:
               - The list MUST contain pharmaceutical products.
               - Known valid products in this domain include: [{anchor_str}].
               - Use this as context to ensure you are preserving valid drugs.
               
            OUTPUT:
            - Return the **cleaned and verified** JSON object with the exact same schema.
            """

            response = self.model.generate_content(prompt)
            
            if response.text:
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    logger.error("Failed to parse AuditorAgent JSON output")
                    return extracted_data
            
            return extracted_data

        except Exception as e:
            logger.error(f"AuditorAgent Failed: {e}")
            return extracted_data
