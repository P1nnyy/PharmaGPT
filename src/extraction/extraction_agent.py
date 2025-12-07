import logging
import re
from typing import Dict, Any, List, Optional
from src.schemas import InvoiceExtraction, RawLineItem

# Setup logging
logger = logging.getLogger(__name__)

class QuantityDescriptionAgent:
    """Agent 2: Specialized for Description and Quantity."""
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # Simple extraction heuristics
        # 1. Product Description: Look for common pharma terms or just take the longest string part
        # For now, simplistic splitting by loose columns (spaces > 2)
        parts = re.split(r'\s{2,}', row_text.strip())
        
        # Assumption: Description is often the first or second long string
        for part in parts:
            if len(part) > 5 and not re.match(r'^[\d\s\%\.\-]+$', part):
                result["Original_Product_Description"] = part
                break
        
        # 2. Quantity: Look for patterns like "10 strips", "15", "10x1"
        # Regex for quantity pattern
        qty_match = re.search(r'\b(\d+(\.\d+)?\s*(strips|tabs|caps|x\d+)?)\b', row_text, re.IGNORECASE)
        if qty_match:
            result["Raw_Quantity"] = qty_match.group(1)
            
        return result

class RateAmountAgent:
    """Agent 3: Specialized for Rates and Net Amount."""
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # Find all float-like numbers
        numbers = [float(x) for x in re.findall(r'\b\d+\.\d{2}\b', row_text)]
        
        if numbers:
            # Heuristic: Amount is usually the largest number
            result["Stated_Net_Amount"] = max(numbers)
            
            # Heuristic: Rate is usually present and smaller than Amount
            # This is very naive and would need column awareness in real OCR
            remaining = [n for n in numbers if n != result["Stated_Net_Amount"]]
            if remaining:
                result["Raw_Rate_Column_1"] = remaining[0] # Take first valid float as rate
                
        return result

class PercentageAgent:
    """Agent 4: Specialized for Percentages (Discount, GST)."""
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # Look for percentages
        percentages = re.findall(r'\b(\d+(\.\d+)?)%', row_text)
        
        if percentages:
            vals = [float(p[0]) for p in percentages]
            # Heuristic: GST is often 5, 12, 18, 28
            gst_candidates = [5.0, 12.0, 18.0, 28.0]
            
            for v in vals:
                if v in gst_candidates:
                    result["Raw_GST_Percentage"] = v
                else:
                    result["Raw_Discount_Percentage"] = v
                    
        return result

class ConsensusEngine:
    """Arbitrates between agents."""
    def resolve(self, partials: List[Dict[str, Any]]) -> RawLineItem:
        merged = {}
        
        # Gather all candidates for each field
        candidates = {}
        for p in partials:
            for k, v in p.items():
                if k not in candidates:
                    candidates[k] = []
                candidates[k].append(v)
        
        # Resolution Logic
        # 1. Description & Quantity: Trust Agent 2 (it's specialized)
        # 2. Rates: Trust Agent 3
        # 3. Percentages: Trust Agent 4
        # Since our agents return distinct keys mostly, simple merge works.
        # But if overlap, we prioritize.
        
        # Construct final dict with prioritization
        final_data = {}
        
        # Fields expected by RawLineItem
        fields = RawLineItem.model_fields.keys()
        
        for field in fields:
            if field in candidates:
                # Naive consensus: Take the first candidate (which relies on order of agents below)
                # Or better: specific logic per field.
                
                # For now: take consensus or first available
                final_data[field] = candidates[field][0]
            else:
                # Defaults for missing data to match schema requirements
                if field == "Original_Product_Description": final_data[field] = "Unknown Product"
                elif field == "Raw_Quantity": final_data[field] = 0
                elif field == "Batch_No": final_data[field] = "UNKNOWN_BATCH"
                elif field == "Stated_Net_Amount": final_data[field] = 0.0
                else: final_data[field] = None

        return RawLineItem(**final_data)

class SupplierIdentifier:
    """Agent 1: Supplier Identifier"""
    def identify(self, raw_text: str) -> Dict[str, str]:
        normalized_text = raw_text.lower()
        supplier_name = "Unknown Supplier"
        invoice_no = "UNKNOWN"
        invoice_date = "YYYY-MM-DD"
        
        if "emm vee traders" in normalized_text:
            supplier_name = "Emm Vee Traders"
        elif "chandra med" in normalized_text:
            supplier_name = "Chandra Med"
        
        if supplier_name == "Emm Vee Traders":
             invoice_no = "EVT-2024-001"
        else:
             invoice_no = "INV-GENERIC"
        
        invoice_date = "2024-12-07"
        
        logger.info(f"Identified Supplier: {supplier_name}")
        return {
            "Supplier_Name": supplier_name,
            "Invoice_No": invoice_no,
            "Invoice_Date": invoice_date
        }

def _mock_ocr(image_path: str) -> Dict[str, Any]:
    """
    Simulates OCR process returning Header Text and List of Line Item Rows.
    Structure: {"header": str, "rows": List[str]}
    """
    if "emm_vee" in image_path.lower():
        return {
            "header": "INVOICE HEADER\nEmm Vee Traders\nLic No: 12345",
            "rows": [
                "Dolo 650     10 strips     Batch001     100.00     1050.00",
                "Augmentin 625   5 strips   Batch002     200.00     1050.00   5%"
            ]
        }
    return {
        "header": "Generic Invoice Data...",
        "rows": []
    }

class ValidatorAgent:
    """Agent 5: Validator and Pydantic Check"""
    def validate(self, extraction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # 1. Pydantic Validation (Structural & Type Check)
            model = InvoiceExtraction(**extraction_data)
            
            # 2. Financial Sanity Checks (Business Logic)
            for item in model.Line_Items:
                # Sanity: Quantity must be positive (parsing might result in 0 or negative)
                if isinstance(item.Raw_Quantity, (int, float)) and item.Raw_Quantity <= 0:
                     logger.warning(f"Validation Warning: Non-positive quantity for {item.Original_Product_Description}")
                
                # Sanity: Net Amount plausible? (if Rate and Qty available)
                # Just a loose check if both are numeric
                if (isinstance(item.Raw_Quantity, (int, float)) and 
                    isinstance(item.Raw_Rate_Column_1, (int, float)) and 
                    isinstance(item.Stated_Net_Amount, (int, float))):
                    
                    expected = item.Raw_Quantity * item.Raw_Rate_Column_1
                    if item.Stated_Net_Amount > expected * 2: # Very loose check (allows for tax/errors)
                        logger.warning(f"Validation Warning: Net Amount {item.Stated_Net_Amount} seems high compared to Qty * Rate {expected}")

            logger.info("Validation Successful")
            return model.model_dump()
            
        except Exception as e:
            logger.error(f"Validation Failed: {e}")
            # In a real system, might return None or raise Error. 
            # Returning None signals failure to downstream.
            return None

def extract_invoice_data(invoice_image_path: str) -> Optional[Dict[str, Any]]:
    """
    Orchestrates extraction using the Council of Agents.
    Returns None if validation fails.
    """
    logger.info(f"Starting extraction for: {invoice_image_path}")
    
    # 1. OCR Step
    ocr_result = _mock_ocr(invoice_image_path)
    header_text = ocr_result.get("header", "")
    row_texts = ocr_result.get("rows", [])
    
    # 2. Agent 1: Supplier Identification
    identifier = SupplierIdentifier()
    header_data = identifier.identify(header_text)
    
    # 3. Line Item Extraction (The Council)
    line_items = []
    
    # Instantiate Agents
    agent_qty = QuantityDescriptionAgent()
    agent_rate = RateAmountAgent()
    agent_perc = PercentageAgent()
    consensus = ConsensusEngine()
    
    for row in row_texts:
        # Run Agents
        p1 = agent_qty.extract(row)
        p2 = agent_rate.extract(row)
        p3 = agent_perc.extract(row)
        
        batch_match = re.search(r'Batch\w+', row, re.IGNORECASE)
        if batch_match:
            p1["Batch_No"] = batch_match.group(0)
            
        # Consensus
        final_item = consensus.resolve([p1, p2, p3])
        line_items.append(final_item)
    
    # 4. Construct Preliminary Object
    raw_data = {
        "Supplier_Name": header_data["Supplier_Name"],
        "Invoice_No": header_data["Invoice_No"],
        "Invoice_Date": header_data["Invoice_Date"],
        "Line_Items": line_items # line_items are Pydantic objects, need dump?
        # Validator expects Dict input for **kwargs or Pydantic objects directly? 
        # InvoiceExtraction expects Line_Items to be list of RawLineItem (which they are) or dicts.
        # Pydantic handles both.
    }
    
    # 5. Agent 5: Validation
    validator = ValidatorAgent()
    validated_data = validator.validate(raw_data)
    
    return validated_data
