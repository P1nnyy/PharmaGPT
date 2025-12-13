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
    OCR Engine using Gemini 2.0 Flash with Structured JSON Output.
    """
    def __init__(self, api_key: str):
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
            # --- Dynamic Prompt Construction (Phase 2) ---
            tables = structure_map.get("tables", [])
            table_instructions = ""
            if tables:
                table_instructions += f"I have detected {len(tables)} distinct tables. Extract data from EACH table sequentially and merge them into the single 'Line_Items' list.\n"
                for i, table in enumerate(tables):
                    headers = ", ".join(f"'{h}'" for h in table.get("detected_headers", []))
                    table_instructions += f"    - **Table {i+1} ({table.get('type', 'Unknown')})**: Located at {table.get('description', 'section')}. Extract using these headers: [{headers}].\n"
            else:
                # Fallback to Phase 1 / Single Table
                headers = structure_map.get("detected_headers", [])
                detected_headers_str = ", ".join(f"'{h}'" for h in headers)
                if headers:
                     table_instructions = f"- **Primary Table**: Identify the main table with headers: [{detected_headers_str}]."

            # 2. Dynamic Mapping for Batch No
            batch_instruction = "Extract the Batch Number."
            try:
                vendor_rules = load_vendor_rules()
                batch_aliases = vendor_rules.get("global_column_aliases", {}).get("Batch_No", [])
            except Exception:
                batch_aliases = ["Pcode", "Batch", "Lot", "Batch No"] # Fallback
            
            # Check headers from all tables
            all_headers = []
            if tables:
                for t in tables:
                     all_headers.extend(t.get("detected_headers", []))
            else:
                all_headers = structure_map.get("detected_headers", [])

            found_batch_col = next((h for h in all_headers if any(alias.lower() in h.lower() for alias in batch_aliases)), None)
            
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
                        "Raw_Discount_Amount": "float or null",
                        "Raw_GST_Percentage": "float or null",
                        "Raw_Taxable_Value": "float or null",
                        "Stated_Net_Amount": "float"
                    }}
                ],
                "Global_Discount_Amount": "float or null",
                "Freight_Charges": "float or null",
                "Round_Off": "float or null",
                "Stated_Grand_Total": "float or null"
            }}

            STRICT INSTRUCTIONS:
            
            1. **Multi-Pass Table Extraction**:
               {table_instructions}
               - **Merge Strategy**: Combine all line items from all tables into the single 'Line_Items' array.
               - **EDGE ITEM RULE**: The first valid item is often immediately below the header, and the last valid item is immediately above the total. Extract ALL rows between the Header and the Footer. Do NOT skip the first or last items.
               - Treat the entire document as a single continuous surface, ignoring distinct visual changes caused by shadows, lighting glares, or folds.
            
            2. **Aggressive Row Extraction**:
               - **Capture ALL Rows**: Capture every single line that looks like a product (has a Quantity and Amount), even if it is isolated or far from the main cluster.
               - **Whitespace Handling**: Do not assume whitespace is a separator. Continue scanning until the Footer.
            
            3. **Financial Disambiguation & GST**:
               - **The 'Qty' Rule**: A valid transaction row MUST have a specific Quantity. If a row contains a 'Rate' but NO 'Qty', it is a Tax/Summary row. IGNORE IT.
               - **CRITICAL GST LOGIC (Split-Tax Summation)**: 
                   - If the table contains separate columns for 'SGST' and 'CGST', you **MUST SUM** their values to populate `Raw_GST_Percentage`. 
                   - **Do not extract just one half.**
                   - **Example**: SGST 2.5% + CGST 2.5% = Extract **5.0** as `Raw_GST_Percentage`.
                   - **Combined GST**: If only a single 'GST' or 'IGST' column exists, map directly to `Raw_GST_Percentage`.
            
            4. **Footer Sweep & Analysis**:
               - **Footer Scan**: After extracting the tables, strictly scan the bottom region of the document.
               - **Specific Fields**:
                   - `Global_Discount_Amount`: Extract 'Cash Discount', 'Scheme Discount', or 'Trade Discount' found in the footer (not line-level).
                   - `Freight_Charges`: Extract any 'Freight', 'Transport', or 'Courier' charges.
                   - `Round_Off`: Extract 'Round Off' or 'Rounding' adjustment.
               - **Logic Check (Net vs Gross)**: 
                   - **Do not confuse 'Gross Amount' (Qty * Rate) with 'Net Amount' (Final Payable).** 
                   - If a column value equals precisely `Qty * Rate`, map it to `Raw_Taxable_Value`. 
                   - `Stated_Net_Amount` MUST be the final effective amount for the line item (often including tax or after discount).
            
            5. **Details & Column Mapping**:
               - **Original_Product_Description**: Extract only the text content found in the 'Particulars' column.
               - **Batch_No**: {batch_instruction}
               - **Raw_HSN_Code**: Extract from columns labeled 'HSN', 'HSN Code', or 'HSN CODE PACK'.
                   - **CRITICAL**: If the column header is 'HSN CODE PACK' or contains both HSN and Pack Size (e.g., '30045039 2 ML' or '30049099 10 S'), you must extract ONLY the numeric HSN code (e.g., '30045039') into Raw_HSN_Code. 
                   - The remaining text ('2 ML', '10 S') is the pack size and should be used to verify Original_Product_Description.
                   - Keep formatting with dots if present (e.g., '3306.10.20'), otherwise keep as pure digits.
               - **Raw_Quantity**: Use the integer value strictly from the column labeled 'Qty' or 'Pack Size'.
               - **Raw_Rate_Column_1**: Identify the specific column labeled 'Rate', 'Billing Rate', 'PTR', or 'PTS'. 
                   - **CRITICAL EXCLUSION**: You must strictly IGNORE any column labeled 'MRP' or 'Maximum Retail Price'. 
                   - **Logic Check**: The Billing Rate is usually lower than the MRP. If two rate-like columns exist, prefer the lower value (which is the billing rate) over the higher value (which is the MRP).
               - **Discount Logic**: 
                   - Check column headers for 'Disc' or 'Dis'. 
                   - If the values are small (e.g., 5.00) and the header implies amount (or no % symbol is present), map to `Raw_Discount_Amount`. 
                   - If '%' is present, map to `Raw_Discount_Percentage`.
               - **Free Quantity Logic**: 
                   - If separate columns exist for 'Qty' and 'Free' (or 'Sch'), extract ONLY the 'Billed' or 'Paid' quantity into `Raw_Quantity`. 
                   - Do NOT add the Free quantity to the Raw_Quantity.
               - **Financial Disambiguation**:
                   - **Distinguish Taxable vs Net**: Explicitly differentiate between 'Taxable Value' (Amount BEFORE Tax) and 'Net Amount' (Amount AFTER Tax).
                   - **Mapping Rule**: Map the column labeled 'Taxable Value', 'Amount', or 'Basic Amt' to `Raw_Taxable_Value`. 
                   - **Net Amount Rule**: Map the final column labeled 'Net Amt', 'Total', or 'Net Payable' to `Stated_Net_Amount`.
                   - **Logic Check**: If you see two amount columns at the end, the smaller one is usually Taxable, and the larger one is Net.
            """
            
            response = self.model.generate_content(
                [
                    {"mime_type": mime_type, "data": image_data},
                    prompt
                ]
            )
            
            if response.text:
                try:
                    txt = response.text.strip()
                    if txt.lower().startswith("```json"):
                        txt = txt[7:]
                    elif txt.startswith("```"):
                        txt = txt[3:]
                    if txt.endswith("```"):
                        txt = txt[:-3]
                    return json.loads(txt.strip())
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Gemini JSON output. Raw text: {txt}")
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
    WARNING: DEPRECATED. Use src.workflow.graph.run_extraction_pipeline instead.
    This function is retained only for legacy unit tests.

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
    
    # --- Multi-Zone Handling (Phase 1 Compatibility) ---
    tables = structure_map.get("tables", [])
    if tables:
        print(f"\n--- Multi-Zone Scout Detection ---")
        for table in tables:
             print(f"Found Table [{table.get('type')}]: {table.get('id')} - {table.get('description')}")
        
        # Compatibility: Use Primary Table headers for the single-pass extraction
        primary_table = next((t for t in tables if t.get("type", "").lower() == "primary"), tables[0])
        structure_map["detected_headers"] = primary_table.get("detected_headers", [])
        print(f"Forwarding Headers from {primary_table.get('id')}: {structure_map['detected_headers']}\n")

    # --- Step 2 & 3: Extractor Agent (Extraction with Dynamic Context) ---
    print("Initializing Agent 2: Extractor")
    logger.info("Initializing Agent 2: Extractor")
    extractor = GeminiExtractorAgent(API_KEY)
    raw_data = extractor.extract_structured(image_path, structure_map=structure_map)
    
    if not raw_data or not raw_data.get("Line_Items"):
         print("Gemini Extractor returned empty. Returning None to trigger 400 error.")
         logger.warning("Gemini Extractor returned empty. Returning None to trigger 400 error.")
         return None
    
    # --- Step 4: Auditor Agent (Verification & Cleaning) ---
    print("Initializing Agent 3: Auditor")
    logger.info("Initializing Agent 3: Auditor")
    auditor = AuditorAgent(API_KEY)
    clean_data = auditor.audit(raw_data)
    print("Auditor finished.")
    
    return clean_data
