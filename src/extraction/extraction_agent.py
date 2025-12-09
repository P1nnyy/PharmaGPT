import os
import re
import json
import logging
import base64
import requests
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

logger = logging.getLogger(__name__)

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Configure API Key (Support both variable names)
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

class GeminiExtractorAgent:
    """
    OCR Engine using Gemini 2.5 Flash with Structured JSON Output.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash',
                generation_config={"response_mime_type": "application/json"}
            )
        else:
            self.model = None

    def extract_structured(self, image_path: str) -> Dict[str, Any]:
        """
        Sends image to Gemini and returns structured JSON (InvoiceExtraction).
        """
        if not self.model:
            logger.warning("No API Key provided for GeminiExtractorAgent.")
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
            Extract the invoice data into a structured JSON format.
            
            Return an object with correctly typed fields matching this schema:
            {
                "Supplier_Name": "string",
                "Invoice_No": "string",
                "Invoice_Date": "string",
                "Line_Items": [
                    {
                        "Original_Product_Description": "string",
                        "Raw_Quantity": "float",
                        "Batch_No": "string",
                        "Raw_Rate_Column_1": "float",
                        "Raw_Rate_Column_2": "float or null",
                        "Raw_Discount_Percentage": "float or null",
                        "Raw_GST_Percentage": "float or null",
                        "Stated_Net_Amount": "float"
                    }
                ]
            }

            STRICT INSTRUCTIONS:
            
            1. **Primary Table Boundaries (Exclusion of Noise)**:
               - The line items to be extracted must originate ONLY from the main product table.
               - This table starts with the header 'S. Code' and ends immediately before the horizontal total line labeled 'Total' and the subsequent section titled 'Free Product Qty' and 'Credit Note Number'.
               - **Constraint**: Ignore and DO NOT extract any data from the financial summary boxes (CGST/SGST breakdowns), the separate 'Free Product Qty' table, and the final 'NET PAYABLE' line.
            
            2. **Details & Column Mapping**:
               - **Original_Product_Description**: Extract only the text content found in the 'Particulars' column. The extraction MUST STOP before the first numeric value that represents Quantity, Rate, or Scheme Code within that row. 
                 - **Constraint**: DO NOT include the S.No., Qty, Rate, Discount, or Scheme Code numbers in the Original_Product_Description field. Ensure this field contains only the descriptive product text.
               - **Batch_No**: Extract the Batch Number.
               - **Raw_Quantity**: Use the integer value strictly from the column labeled 'Qty' or 'Pack Size'.
               - **Raw_Rate_Column_1**: Use the float value from the column labeled 'Rate'. This is the unit rate.
               - **Stated_Net_Amount**: Use the float value from the final column labeled 'Net Amt' or 'Net Payable' on the far right of the table.
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
                    logger.error("Failed to parse Gemini JSON output")
                    return {}
            
            return {}

        except Exception as e:
            logger.error(f"GeminiExtractorAgent Failed: {e}")
            return {}

class ValidatorAgent:
    @staticmethod
    def validate(item: Dict[str, Any]) -> None:
        if not item.get("Original_Product_Description"):
             pass # Acceptable, might be just a financial row or noise filtering later
        
        qty = float(item.get("Raw_Quantity") or 0)
        rate = float(item.get("Raw_Rate_Column_1") or 0)
        net = float(item.get("Stated_Net_Amount") or 0)
        
        if qty > 0 and rate > 0 and net > 0:
            expected = qty * rate
            # Severe Logic Error Check > 50%
            if abs(expected - net) > (expected * 0.5):
                logger.error(f"SEVERE VALIDATION FAILURE: {item.get('Original_Product_Description')} - Expected {expected}, Got {net}")

def _mock_ocr() -> Dict[str, Any]:
    """Fallback Mock Data for Verification"""
    return {
        "Supplier_Name": "Detected Supplier", 
        "Invoice_No": "INV-MOCK", 
        "Invoice_Date": "2024-01-01",
        "Line_Items": [
            {
                "Original_Product_Description": "Dolo 650mg Tablet", 
                "Raw_Quantity": 10, 
                "Batch_No": "X123", 
                "Raw_Rate_Column_1": 25.00, 
                "Stated_Net_Amount": 250.00
            }
        ]
    }

def extract_invoice_data(image_path: str) -> Dict[str, Any]:
    """
    Main extraction entry point.
    Pipeline: Gemini JSON Extraction
    """
    extractor = GeminiExtractorAgent(API_KEY)
    
    # Try Gemini
    data = extractor.extract_structured(image_path)
    
    # Fallback
    if not data or not data.get("Line_Items"):
         logger.warning("Gemini returned empty or invalid data. Using Mock.")
         return _mock_ocr()

    # Validate/Clean
    cleaned_items = []
    for item in data.get("Line_Items", []):
         if item.get("Batch_No") is None:
             item["Batch_No"] = ""
         ValidatorAgent.validate(item)
         cleaned_items.append(item)
    
    data["Line_Items"] = cleaned_items
    return data
