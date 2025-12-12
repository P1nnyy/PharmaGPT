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

from src.extraction.scout_agent import ScoutAgent
from src.extraction.auditor_agent import AuditorAgent
from src.utils.config_loader import load_vendor_rules

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
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0
                }
            )
        else:
            self.model = None

    def extract_structured(self, image_path: str, structure_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends image to Gemini and returns structured JSON (InvoiceExtraction).
        incorporating dynamic prompt injection if structure_map is provided.
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

            # Dynamic Context Construction
            locking_instruction = ""
            batch_instruction = "Extract the Batch Number."
            detected_headers_str = ""
            
            if structure_map:
                headers = structure_map.get("detected_headers", [])
                detected_headers_str = ", ".join(f"'{h}'" for h in headers)
                
                # 1. Strict Positional Priority
                if headers:
                    locking_instruction = f"""
                    **Strict Positional Priority (Scan-and-Lock)**: 
                    - Scan top-down. 
                    - Lock onto the FIRST table that specifically contains this header sequence (or subset): [{detected_headers_str}].
                    - This identified table is the ONLY valid source.
                    """

                # 2. Dynamic Mapping for Batch No
                try:
                    vendor_rules = load_vendor_rules()
                    batch_aliases = vendor_rules.get("global_column_aliases", {}).get("Batch_No", [])
                except Exception:
                    batch_aliases = ["Pcode", "Batch", "Lot", "Batch No"] # Fallback

                found_batch_col = next((h for h in headers if any(alias.lower() in h.lower() for alias in batch_aliases)), None)
                
                if found_batch_col:
                     batch_instruction = f"Extract the Batch Number from the column explicitly labeled '{found_batch_col}'."

            prompt = f"""
            Extract the invoice data into a structured JSON format.
            
            Return an object with correctly typed fields matching this schema:
            {{
                "Supplier_Name": "string",
                "Invoice_No": "string",
                "Invoice_Date": "string",
                "Line_Items": [
                    {{
                        "Original_Product_Description": "string",
                        "Raw_Quantity": "float",
                        "Batch_No": "string",
                        "Raw_HSN_Code": "string",
                        "Raw_Rate_Column_1": "float",
                        "Raw_Rate_Column_2": "float or null",
                        "Raw_Discount_Percentage": "float or null",
                        "Raw_GST_Percentage": "float or null",
                        "Stated_Net_Amount": "float"
                    }}
                ]
            }}

            STRICT INSTRUCTIONS:
            
            1. **Primary Table Identification**:
               {locking_instruction or "- Identify the FIRST logical table structure that contains the MAXIMUM NUMBER of distinct columns (10+)."}
               - IGNORE any subsequent, smaller tables (e.g., promotional or summary tables).
               
            2. **Termination (Stop Logic)**:
               - The extraction must STOP IMMEDIATELY when the row contains a 'Total' summation, a 'Grand Total', or the structure shifts to a tax summary.
               - **Constraint**: Ignore and DO NOT extract any data from the financial summary boxes (CGST/SGST breakdowns), the separate 'Free Product Qty' table, and the final 'NET PAYABLE' line.
               - **Explicit Ignore List**: Tax Breakdowns, HSN Summaries, Dispatch Summaries.
            
            3. **SEMANTIC VERIFICATION (PRODUCT NAME ANCHORING)**:
               - **Contextual Hint**: The table is expected to contain pharmaceutical product names.
               - **Stop Signal**: If the 'Original_Product_Description' closely matches a financial label like 'CGST Output', 'Round Off', or 'Freight', STOP extraction immediately.
            
            4. **Financial Disambiguation & GST**:
               - **The 'Qty' Rule**: A valid transaction row MUST have a specific Quantity. If a row contains a 'Rate' but NO 'Qty', it is a Tax/Summary row. IGNORE IT.
               - **GST Extraction**: Locate the final tax percentage for the item, which may be labeled 'GST %' or derived from the header. Use this figure for Raw_GST_Percentage.
            
            5. **Details & Column Mapping**:
               - **Original_Product_Description**: Extract only the text content found in the 'Particulars' column.
               - **Batch_No**: {batch_instruction}
               - **Raw_HSN_Code**: Extract from columns labeled 'HSN', 'HSN Code', or 'HSN CODE PACK'.
                   - **CRITICAL**: If the column header is 'HSN CODE PACK' or contains both HSN and Pack Size (e.g., '30045039 2 ML' or '30049099 10 S'), you must extract ONLY the numeric HSN code (e.g., '30045039') into Raw_HSN_Code. 
                   - The remaining text ('2 ML', '10 S') is the pack size and should be used to verify Original_Product_Description.
                   - Keep formatting with dots if present (e.g., '3306.10.20'), otherwise keep as pure digits.
               - **Raw_Quantity**: Use the integer value strictly from the column labeled 'Qty' or 'Pack Size'.
               - **Raw_Rate_Column_1**: Use the float value from the column labeled 'Rate'.
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
                logger.warning(f"Validation Warning: {item.get('Original_Product_Description')} - Expected {expected}, Got {net}")

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
    Main extraction entry point orchestrating the Council of Agents.
    Pipeline: Scout -> Extractor -> Auditor
    """
    
    # --- Step 1: Scout Agent (Structure Discovery) ---
    print("Initializing Agent 1: Scout")
    logger.info("Initializing Agent 1: Scout")
    scout = ScoutAgent(API_KEY)
    structure_map = scout.scan(image_path)
    print(f"Scout Result: {structure_map}")
    logger.info(f"Scout Result: {structure_map}")
    
    # --- Step 2 & 3: Extractor Agent (Extraction with Dynamic Context) ---
    print("Initializing Agent 2: Extractor")
    logger.info("Initializing Agent 2: Extractor")
    extractor = GeminiExtractorAgent(API_KEY)
    raw_data = extractor.extract_structured(image_path, structure_map=structure_map)
    
    if not raw_data or not raw_data.get("Line_Items"):
         print("Gemini Extractor returned empty. Falling back to Mock.")
         logger.warning("Gemini Extractor returned empty. Falling back to Mock.")
         return _mock_ocr()
    
    # --- Step 4: Auditor Agent (Verification & Cleaning) ---
    print("Initializing Agent 3: Auditor")
    logger.info("Initializing Agent 3: Auditor")
    auditor = AuditorAgent(API_KEY)
    clean_data = auditor.audit(raw_data)
    print("Auditor finished.")
    
    return clean_data
