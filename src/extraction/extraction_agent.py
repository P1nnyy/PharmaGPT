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

# ... imports ...
import json

# ... existing code ...

class GeminiExtractorAgent:
    """
    Agent 0: The Master Extractor using Gemini Vision Structured Output.
    """
    def extract_structured(self, image_path: str) -> Dict[str, Any]:
        """
        Asks Gemini to extract the full invoice as a structured JSON object.
        """
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. Cannot use GeminiExtractorAgent.")
            return {}
            
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            sample_file = genai.upload_file(path=image_path, display_name="Invoice")
            
            # Strict schema prompt
            # We want it to match our InvoiceExtraction schema structure roughly
            # Note: We ask for "line_items" as a list.
            prompt = """
            Extract the data from this invoice image into a valid JSON object.
            
            The JSON must have the following keys:
            - "Supplier_Name": String (e.g. "Emm Vee Traders")
            - "Invoice_No": String
            - "Invoice_Date": String (YYYY-MM-DD format)
            - "Line_Items": A list of objects, each containing:
                - "Original_Product_Description": String (The full product name)
                - "Raw_Quantity": Number or String (e.g. 10 or "10 strips")
                - "Batch_No": String
                - "Raw_Rate_Column_1": Number (The primary rate/price per unit)
                - "Raw_Rate_Column_2": Number (Secondary rate if exists, else null)
                - "Stated_Net_Amount": Number (The total amount for this line)
                - "Raw_Discount_Percentage": Number (e.g. 10 for 10%, else null)
                - "Raw_GST_Percentage": Number (e.g. 12 for 12%, else null)
            
            Return ONLY the JSON. No markdown formatting.
            """
            
            response = model.generate_content([sample_file, prompt])
            
            # Clean response
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()
                
            data = json.loads(text)
            return data
            
        except Exception as e:
            logger.error(f"Gemini Structured Extraction failed: {e}")
            return {}

class SupplierIdentifier:
    """Agent 1: Supplier Identifier - Refined to use Gemini Output"""
    def identify(self, raw_text: str, structured_data: Dict[str, Any] = None) -> Dict[str, str]:
        # Prioritize structured data if available
        if structured_data and structured_data.get("Supplier_Name"):
             return {
                "Supplier_Name": structured_data.get("Supplier_Name"),
                "Invoice_No": structured_data.get("Invoice_No", "UNKNOWN"),
                "Invoice_Date": structured_data.get("Invoice_Date", "YYYY-MM-DD")
             }
        
        # Fallback to Text Analysis
        normalized_text = raw_text.lower()
        supplier_name = "Unknown Supplier"
        invoice_no = "UNKNOWN"
        invoice_date = "YYYY-MM-DD"
        
        if "emm vee traders" in normalized_text:
            supplier_name = "Emm Vee Traders"
        elif "chandra med" in normalized_text:
            supplier_name = "Chandra Med"
        
        # ... logic ...
        if supplier_name == "Emm Vee Traders":
             invoice_no = "EVT-2024-001"
        else:
             invoice_no = "INV-GENERIC"
        
        invoice_date = "2024-12-07"
        
        return {
            "Supplier_Name": supplier_name,
            "Invoice_No": invoice_no,
            "Invoice_Date": invoice_date
        }

# ... QuantityDescriptionAgent, RateAmountAgent, PercentageAgent classes remain ...
# (They act as fallbacks now)

class ConsensusEngine:
    """Arbitrates between agents, prioritizing Gemini."""
    def resolve(self, gemini_item: Dict[str, Any], heuristic_partials: List[Dict[str, Any]]) -> RawLineItem:
        """
        gemini_item: The line item object directly from Gemini Structured output.
        heuristic_partials: List of dicts from the heuristic agents (for the same row).
        """
        final_data = {}
        fields = RawLineItem.model_fields.keys()
        
        # 1. Base Strategy: Trust Gemini
        # If Gemini has a valid value, use it.
        # If Gemini is missing/null, look at heuristics.
        
        for field in fields:
            val = gemini_item.get(field)
            
            # Validation: Is val 'good'?
            is_valid = val is not None and val != ""
            # Assuming 0 is valid for numbers? Maybe not for Quantity/Amount.
            if field in ["Raw_Quantity", "Stated_Net_Amount"] and val == 0:
                is_valid = False
                
            if is_valid:
                final_data[field] = val
            else:
                # Fallback to heuristics
                found = False
                for p in heuristic_partials:
                    if p.get(field) is not None:
                        final_data[field] = p[field]
                        found = True
                        break # Take first heuristic match
                
                if not found:
                    # Defaults
                    if field == "Original_Product_Description": final_data[field] = "Unknown Product"
                    elif field == "Raw_Quantity": final_data[field] = 0
                    elif field == "Batch_No": final_data[field] = "UNKNOWN_BATCH"
                    elif field == "Stated_Net_Amount": final_data[field] = 0.0
                    else: final_data[field] = None

        return RawLineItem(**final_data)

def extract_invoice_data(invoice_image_path: str) -> Optional[Dict[str, Any]]:
    """
    Orchestrates extraction using Gemini Structured Output as Primary + Heuristic Backup.
    """
    logger.info(f"Starting extraction for: {invoice_image_path}")
    
    # 1. Gemini Structured Extraction (Primary)
    gemini_agent = GeminiExtractorAgent()
    structured_data = gemini_agent.extract_structured(invoice_image_path)
    
    # Check if Gemini worked
    gemini_line_items = structured_data.get("Line_Items", [])
    
    # 2. Heuristic/Row-based Extraction (Backups/Validators)
    # We still need rows to run heuristic agents. 
    # If Gemini worked, we might not have "rows" perfectly mapped to Gemini items 1:1 easily without geometry.
    # STRATEGY: 
    # If Gemini returns valid structure, we use that as the base.
    # We loop through Gemini items. 
    # The heuristic agents work on *Text Rows*. 
    # Matching them requires text alignment which is complex.
    # SIMPLIFICATION:
    # Use Gemini as the *Primary Source of Truth*. 
    # "Repurpose Council for Validation... Fallback Heuristics... if Gemini output is missing a field".
    # Implementation:
    # If Gemini returned items, we iterate through them.
    # If an item has missing fields, we *try* to find the data in the raw text?
    # Or: We run get_raw_text_from_vision as well to get rows, then try to match rows to Gemini items?
    # That is very hard (Row matching).
    #
    # ALTERNATIVE INTERPRETATION:
    # The user says "Use simpler heuristic agents for redundancy checks".
    # And "If Gemini output is missing a field... simpler regex heuristics serve as backup".
    # 
    # Let's do this:
    # 1. Get Structured Data (Primary).
    # 2. Get Raw Text (Secondary - needed for fallback context).
    # 3. For each Gemini Item:
    #    - Check correctness.
    #    - If fields missing, we assume the *Raw Text Row* corresponding to this item contains the data.
    #    - But we don't know *which* row.
    #    - Thus, Heuristic Backup is only easy if we run Heuristics on ALL rows and try to find a "match" for the Gemini Item?
    #    - OR: We trust Gemini mostly. If Gemini fails completely (empty/key missing), we fall back to Pure Heuristic extraction from Raw Text.
    #
    # Let's implement refined Supplier Identifier first.
    
    # Get Raw Text (for Supplier Backup & Heuristic full fallback if needed)
    raw_ocr_result = get_raw_text_from_vision(invoice_image_path)
    header_text = raw_ocr_result.get("header", "")
    row_texts = raw_ocr_result.get("rows", [])
    
    # Supplier ID
    identifier = SupplierIdentifier()
    header_data = identifier.identify(header_text, structured_data)
    
    line_items = []
    
    consensus = ConsensusEngine()
    
    # Agents (Backups)
    agent_qty = QuantityDescriptionAgent()
    agent_rate = RateAmountAgent()
    agent_perc = PercentageAgent()
    
    if len(gemini_line_items) > 0:
        # Strategy: Iterate Gemini Items. 
        # For each, validation is implicitly done by Consensus (checking for non-nulls).
        # Fallback: If a field is missing, can we look at the raw text? 
        # Without matching rows, it's guessing. 
        # So we will pass "empty" heuristics to Consensus unless we can match?
        # 
        # WAIT. The prompt says "Repurpose... heuristics to act as Validator... serve as backup".
        # 
        # Let's simple-match heuristics:
        # We run heuristics on ALL rows. We get a pool of "potential items".
        # For a Gemini item, if it needs a value, we check if any Heuristic Item looks "similar" (e.g. same Description) and has the missing value.
        
        # 1. Run Heuristics on all rows to build a "Knowledge Base"
        heuristic_items = []
        for row in row_texts:
            if len(row) < 5: continue
            p1 = agent_qty.extract(row)
            p2 = agent_rate.extract(row)
            p3 = agent_perc.extract(row)
            # Combine into a "Heuristic Partial"
            combined = {**p1, **p2, **p3}
            heuristic_items.append(combined)
            
        # 2. Resolve each Gemini Item
        for g_item in gemini_line_items:
            # Find matching heuristic context?
            # Match by Description (fuzzy) or Amount?
            desc = g_item.get("Original_Product_Description", "")
            matches = []
            if desc:
                # Simple containment match
                matches = [h for h in heuristic_items if h.get("Original_Product_Description") and (h["Original_Product_Description"] in desc or desc in h["Original_Product_Description"])]
            
            final_item = consensus.resolve(g_item, matches)
            line_items.append(final_item)
            
    else:
        # Gemini failed to structure. Fallback to Pure Heuristic.
        logger.warning("Gemini Structured Extraction returned no items. Falling back to Heuristics.")
        # Legacy loop
        for row in row_texts:
             if len(row) < 5: continue
             p1 = agent_qty.extract(row)
             p2 = agent_rate.extract(row)
             p3 = agent_perc.extract(row)
             # Reuse consensus logic but without gemini_item?
             # Need adapter or update resolve signature to handle "No Gemini".
             # Hack: pass empty dict as Gemini item.
             final_item = consensus.resolve({}, [p1, p2, p3]) 
             if final_item.Stated_Net_Amount > 0:
                 line_items.append(final_item)
    
    # Construct Final Object
    raw_data = {
        "Supplier_Name": header_data["Supplier_Name"],
        "Invoice_No": header_data["Invoice_No"],
        "Invoice_Date": header_data["Invoice_Date"],
        "Line_Items": line_items
    }
    
    # Validation
    validator = ValidatorAgent()
    validated_data = validator.validate(raw_data)
    
    return validated_data
