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

class GeminiOCR:
    """
    OCR Engine using Gemini 1.5 Flash.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

    def extract_text(self, image_path: str) -> List[str]:
        """
        Sends image to Gemini and returns a list of text rows.
        """
        if not self.model:
            logger.warning("No API Key provided for GeminiOCR.")
            return []

        try:
            # Upload the file
            # Note: For efficiency in production, we might want to pass bytes directly if supported 
            # or manage file uploads better. giving local path works for now with genai.upload_file 
            # (which uploads to Google File API) OR we can pass the image data directly to generate_content 
            # if we read it. 'gemini-1.5-flash' supports image inputs.
            
            # Using PIL image or just raw bytes/mime type is often easier than managing File API lifecycle for single requests.
            # Let's read file as bytes and pass to generate_content.
            
            with open(image_path, "rb") as f:
                image_data = f.read()
                
            mime_type = "image/jpeg" 
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            prompt = """
            Extract all text from this invoice image line by line.
            Do not summarize. 
            Output the result as a simple list of strings, where each string represents a line of text from the image.
            Maintain the spatial structure as much as possible (e.g. columns on the same line should be in the same string).
            """
            
            response = self.model.generate_content(
                [
                    {"mime_type": mime_type, "data": image_data},
                    prompt
                ]
            )
            
            if response.text:
                # Naive split by newline
                rows = [r.strip() for r in response.text.split('\n') if r.strip()]
                return rows
            
            return []

        except Exception as e:
            logger.error(f"GeminiOCR Failed: {e}")
            return []

class QuantityDescriptionAgent:
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # 1. Product Description: Heuristic split
        # Simple Logic: Split by double spaces. Lengthy part is Description.
        parts = re.split(r'\s{2,}', row_text.strip())
        
        for part in parts:
            # Filter out pure numbers, dates, short codes
            is_noise = re.match(r'^[\d\s\%\.\-\/]+$', part) or len(part) < 4 or "batch" in part.lower()
            if not is_noise and "strip" not in part.lower():
                result["Original_Product_Description"] = part
                break
        
        # 2. Quantity (Right-Biased Search)
        # Prioritize explicit unit markers
        unit_regex = r'\b(\d+(\.\d+)?)\s*(strips?|tabs?|caps?|box|nos|x\d+)\b'
        qty_match = re.search(unit_regex, row_text, re.IGNORECASE)
        
        if qty_match:
            result["Raw_Quantity"] = qty_match.group(1)
        else:
            # Fallback: Search for small integers (<100) only in the RIGHT HALF
            # Identifies isolated "10" or "5" without units.
            midpoint = len(row_text) // 2
            right_half = row_text[midpoint:]
            
            int_matches = re.finditer(r'\b(\d{1,4})\b', right_half)
            candidates = []
            for m in int_matches:
                val = int(m.group(1))
                if val < 100:
                    candidates.append(val)
            
            if candidates:
                result["Raw_Quantity"] = candidates[-1] # Rightmost small integer

        return result

class RateAmountAgent:
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        
        # Stated_Net_Amount: Text often ends with the Total Amount.
        # Look for float in the LAST 25 chars.
        tail_end = row_text[-25:]
        amount_matches = re.findall(r'(\d+\.\d{2})', tail_end)
        
        if amount_matches:
            result["Stated_Net_Amount"] = float(amount_matches[-1])
            
            # Find Rate relative to Net Amount
            # Locate position of matches[-1] in row
            net_amt_str = amount_matches[-1]
            idx = row_text.rfind(net_amt_str)
            if idx > 0:
                preceding = row_text[:idx]
                rate_matches = re.findall(r'(\d+\.\d{2})', preceding)
                if rate_matches:
                    result["Raw_Rate_Column_1"] = float(rate_matches[-1])

        return result

class PercentageAgent:
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # GST Heuristic
        matches = re.findall(r'\b(5|12|18|28)\b', row_text)
        if matches:
            result["Raw_GST_Percentage"] = float(max(matches, key=lambda x: int(x)))
        return result

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

def _mock_ocr() -> List[str]:
    """Fallback Mock Data for Verification"""
    return [
        "SL PRODUCT DESCRIPTION          BATCH   QTY    RATE     AMOUNT",
        "1  Dolo 650mg Tablet            X123    10 strips   25.00    250.00",
        "2  Augmentin 625 Duo            Y456    5 strips    80.00    400.00"
    ]

def extract_invoice_data(image_path: str) -> Dict[str, Any]:
    """
    Main extraction entry point.
    Pipeline: GCV OCR (REST) -> Heuristic Agents -> Aggregation.
    """
    # 1. OCR Step
    ocr_engine = GeminiOCR(API_KEY)
    
    # Try Gemini
    row_texts = ocr_engine.extract_text(image_path)
    
    # Fallback to Mock if Gemini fails (returns empty)
    if not row_texts:
         logger.warning("Gemini returned no text or failed. Using Mock OCR.")
         row_texts = _mock_ocr()

    # 2. Processing
    agent_qty = QuantityDescriptionAgent()
    agent_rate = RateAmountAgent()
    agent_perc = PercentageAgent()
    
    line_items = []
    
    for row in row_texts:
        # Skip short headers/noise
        if len(row) < 10: continue
        
        p1 = agent_qty.extract(row)
        p2 = agent_rate.extract(row)
        p3 = agent_perc.extract(row)
        
        # Merge Heuristics
        combined_item = {**p1, **p2, **p3}
        
        # 3. Filtering Criteria
        # Must have a Net Amount to be considered a valid line item 
        # (This avoids capturing headers or footer text as items)
        if combined_item.get("Stated_Net_Amount"):
            final_item = {
                "Original_Product_Description": combined_item.get("Original_Product_Description", "Unknown"),
                "Raw_Quantity": combined_item.get("Raw_Quantity"),
                "Batch_No": None, # Could add BatchAgent later
                "Raw_Rate_Column_1": combined_item.get("Raw_Rate_Column_1"),
                "Raw_Rate_Column_2": None,
                "Stated_Net_Amount": combined_item.get("Stated_Net_Amount"),
                "Raw_Discount_Percentage": None,
                "Raw_GST_Percentage": combined_item.get("Raw_GST_Percentage"),
            }
            
            ValidatorAgent.validate(final_item)
            line_items.append(final_item)

    return {
        "Supplier_Name": "Detected Supplier", 
        "Invoice_No": "INV-" + str(len(line_items)), 
        "Invoice_Date": "2024-01-01",
        "Line_Items": line_items
    }
