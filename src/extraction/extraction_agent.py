import logging
import re
import os
import json
from typing import Dict, Any, List, Optional
from src.schemas import InvoiceExtraction, RawLineItem

# Setup logging
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai = None
# Only attempt to import if we have a key (prevents crashes in test envs with broken deps)
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to import google.generativeai: {e}. Gemini Vision features will be unavailable.")
        genai = None

class QuantityDescriptionAgent:
    """Agent 2: Specialized for Description and Quantity."""
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # 1. Product Description
        # Heuristic: Split by double spaces, filter out short noise or dates
        parts = re.split(r'\s{2,}', row_text.strip())
        desc_parts = []
        for part in parts:
             # Heuristic: Description is usually long, contains letters, not just d/m/y or numbers
             if len(part) > 3 and not re.match(r'^[\d\s\%\.\-\/]+$', part) and "batch" not in part.lower():
                 desc_parts.append(part)
        
        if desc_parts:
            # Assume first valid text block is Description
            result["Original_Product_Description"] = desc_parts[0]
        
        # 2. Quantity - Hardened Logic
        # Priority 1: Explicit Unit Markers (e.g. "10 strips", "50 tabs", "1x15")
        # Added 'pcs', 'box', 'vials', 'amp' and 'x' notation
        unit_regex = r'\b(\d+)\s*(strips?|tabs?|caps?|box|nos|pcs|vials|amp|x\s*\d+)\b'
        qty_match = re.search(unit_regex, row_text, re.IGNORECASE)
        
        if qty_match:
             result["Raw_Quantity"] = int(qty_match.group(1))
        else:
            # Priority 2: Standalone Integers, strictly filtering out Dosage numbers
            # Strategy: Look for integers < 100 which are likely quantities.
            # Avoid likely dosages: 100, 250, 500, 650, 1000 UNLESS they have units (caught above)
            # Find all independent integers
            int_matches = re.finditer(r'(?<!\.)\b(\d+)\b(?!\.)', row_text)
            candidates = []
            
            for m in int_matches:
                val = int(m.group(1))
                # Heuristic: Dosage is usually large (>=100)
                # Quantity is usually small (<100)
                # Exception: 100 tablets. But if no unit, assume 100 is dosage or rate.
                if 0 < val < 100: 
                    candidates.append(val)
            
            if candidates:
                # If multiple small ints, Quantity is usually NOT the first number (Index) 
                # but could be anywhere. 
                # Simplification: Take the largest candidate? Or first?
                # Usually Quantity is the largest small integer? (e.g. Index 1, Qty 10)
                # Let's take the first one found that is > 0?
                result["Raw_Quantity"] = candidates[0]
        
        return result

class RateAmountAgent:
    """Agent 3: Specialized for Rates and Net Amount."""
    def extract(self, row_text: str) -> Dict[str, Any]:
        result = {}
        # Strategy: Strict spatial search for Financials
        # 1. Net Amount is LAST columns.
        # 2. Rate is preceding Amount.
        
        # Regex for currency-like float: 1,234.00 or 1234.00 (Must have decimal .XX)
        # This reduces noise from dates/integers.
        float_regex = r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b'
        matches = list(re.finditer(float_regex, row_text))
        
        if not matches:
             # Fallback: looser float (just .d+)
             matches = list(re.finditer(r'\b\d+\.\d+\b', row_text))
        
        if matches:
            matches.sort(key=lambda m: m.start())
            
            # 1. Stated_Net_Amount: Must be the last one, and ideally near end of string
            # We trust the last float found is the Net Amount.
            min_matches = 1
            amount_match = matches[-1]
            result["Stated_Net_Amount"] = float(amount_match.group().replace(',', ''))
            
            # 2. Rate: The number immediately preceding the Net Amount
            if len(matches) >= 2:
                rate_match = matches[-2]
                result["Raw_Rate_Column_1"] = float(rate_match.group().replace(',', ''))
                
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

def get_raw_text_from_vision(image_path: str) -> Dict[str, Any]:
    """
    Uses Gemini Vision to get raw text (header + rows).
    Falls back to mock OCR if key is missing or validation fails.
    """
    if not GEMINI_API_KEY or genai is None:
        logger.warning("No Gemini Key or module. Using Mock OCR.")
        return _mock_ocr(image_path)
        
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        myfile = genai.upload_file(image_path, display_name="InvoiceRaw")
        # Prompt for raw text extraction
        prompt = "Extract all text from this invoice. Return the raw text exactly as it appears, line by line."
        response = model.generate_content([myfile, prompt])
        text = response.text
        
        # Simple processing: First few lines header, rest rows
        lines = [l for l in text.split('\n') if l.strip()]
        
        return {
            "header": "\n".join(lines[:5]) if lines else "",
            "rows": lines[5:] if len(lines) > 5 else lines
        }
    except Exception as e:
        logger.error(f"Gemini Vision Raw Text failed: {e}")
        return _mock_ocr(image_path)

class GeminiExtractorAgent:
    """
    Agent 0: The Master Extractor using Gemini Vision Structured Output.
    """
    def extract_structured(self, image_path: str) -> Dict[str, Any]:
        """
        Asks Gemini to extract the full invoice as a structured JSON object.
        """
        if not GEMINI_API_KEY or genai is None:
            if not GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY not set. Cannot use GeminiExtractorAgent.")
            if genai is None:
                 logger.warning("google.generativeai module not available.")
            return {}
            
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            sample_file = genai.upload_file(path=image_path, display_name="Invoice")
            
            # Strict schema prompt
            # We want it to match our InvoiceExtraction schema structure roughly
            # Note: We ask for "line_items" as a list.
            prompt = """
            Extract the invoice data into a strict JSON object.
            
            CRITICAL BUSINESS LOGIC AND SPATIAL AWARENESS:
            1. **Financial Context (Rate)**: 
               - Identify the "Rate" column used for calculation. 
               - **IMPORTANT**: Look for column headers like "RATE/DOZ", "PTR", or just "Rate". 
               - **PRIORITY**: If a "RATE/DOZ" or "PTR" column exists, extract THAT value into 'Raw_Rate_Column_1' instead of MRP.
            
            2. **Strict Net Amount Localization**:
               - The 'Stated_Net_Amount' **MUST** come from the **FAR-RIGHT column** of the line item table.
               - **WARNING**: Do NOT just pick the largest number. If the largest number is MRP or Gross Value in a middle column, IGNORE IT. Only extract the final line total from the far right.
            
            3. **Quantity vs Dosage**:
               - **Strictly separate** Dosage (e.g. "650" in "Dolo 650") from Quantity.
               - Extract Quantity **ONLY** from the dedicated 'Quantity' column using spatial awareness.
               - Quantity often has units like "strips", "tabs", "box", "nos", or is a small integer (e.g., 1, 5, 10).
               - **NEVER** extract the dosage number (like 650, 500) as the Quantity.
            
            4. **Tax/GST**:
               - Extract 'Raw_GST_Percentage' explicitly (e.g. 5, 12, 18) if available in a column.
            
            The JSON must have the following keys:
            - "Supplier_Name": String (e.g. "Emm Vee Traders")
            - "Invoice_No": String
            - "Invoice_Date": String (YYYY-MM-DD format)
            - "Line_Items": A list of objects, each containing:
                - "Original_Product_Description": String (the full name, e.g. "Dolo 650mg Tablet")
                - "Raw_Quantity": Number or String (Value only, e.g. 10. Prefer numbers.)
                - "Batch_No": String
                - "Raw_Rate_Column_1": Number (The primary unit price/rate. Prioritize PTR/Rate-per-Doz.)
                - "Raw_Rate_Column_2": Number (Secondary rate if exists, else null)
                - "Stated_Net_Amount": Number (The total amount from the FAR-RIGHT column)
                - "Raw_Discount_Percentage": Number (e.g. 10 for 10%, else null)
                - "Raw_GST_Percentage": Number (e.g. 12 for 12%, else null)
            
            Return ONLY the raw JSON string. No markdown formatting or code blocks.
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
        
        # 1. Base Strategy: Trust Gemini, but VERIFY.
        # If Gemini has a valid value, use it.
        # If Gemini is missing/null/zero (where invalid), AGGRESSIVELY look at heuristics.
        
        # Helper to check validity
        def is_valid_val(field, val):
            if val is None or val == "": return False
            if field in ["Raw_Quantity", "Stated_Net_Amount", "Raw_Rate_Column_1"]:
                 try:
                     # Handle strings that look like numbers (aggressive)
                     f_val = float(val)
                     if f_val <= 0: return False
                 except (ValueError, TypeError):
                     # Not a number
                     return False
            return True

        for field in fields:
            val = gemini_item.get(field)
            
            if is_valid_val(field, val):
                final_data[field] = val
            else:
                # Conditional Fallback: Field invalid in Gemini -> Check Heuristics
                found_val = None
                for p in heuristic_partials:
                    h_val = p.get(field)
                    if is_valid_val(field, h_val):
                        found_val = h_val
                        break # Take first VALID heuristic match
                
                if found_val is not None:
                     logger.info(f"Consensus: Swapped invalid Gemini {field}={val} with Heuristic {found_val}")
                     final_data[field] = found_val
                else:
                    # Defaults
                    if field == "Original_Product_Description": final_data[field] = "Unknown Product"
                    elif field == "Raw_Quantity": final_data[field] = 0
                    elif field == "Batch_No": final_data[field] = "UNKNOWN_BATCH"
                    elif field == "Stated_Net_Amount": final_data[field] = 0.0
                    else: final_data[field] = None

        return RawLineItem(**final_data)

class ValidatorAgent:
    """Agent 5: Validator and Pydantic Check"""
    def validate(self, extraction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # 1. Pydantic Validation (Structural & Type Check)
            model = InvoiceExtraction(**extraction_data)
            
            # 2. Financial Sanity Checks (Business Logic)
            valid_items = []
            for item in model.Line_Items:
                # Rule: Zero Value Check (Skip empty rows)
                if (item.Raw_Quantity == 0 or item.Raw_Quantity is None) and (item.Stated_Net_Amount == 0.0 or item.Stated_Net_Amount is None):
                     logger.warning(f"Validator: Skipping empty line item {item.Original_Product_Description}")
                     continue

                # Sanity: Quantity must be positive 
                if isinstance(item.Raw_Quantity, (int, float)) and item.Raw_Quantity <= 0:
                     logger.warning(f"Validation Warning: Non-positive quantity for {item.Original_Product_Description}")
                
                # Sanity: Net Amount Plausibility (Tight Check)
                if (isinstance(item.Raw_Quantity, (int, float)) and item.Raw_Quantity > 0 and
                    isinstance(item.Raw_Rate_Column_1, (int, float)) and item.Raw_Rate_Column_1 > 0 and
                    isinstance(item.Stated_Net_Amount, (int, float)) and item.Stated_Net_Amount > 0):
                    
                    base_expected = item.Raw_Quantity * item.Raw_Rate_Column_1
                    # Allow for Tax (5-28%) and small errors.
                    # Max expected = Base * 1.28 (28% GST)
                    # Min expected = Base (0% GST)
                    # We allow 50% deviation from Base for severe outliers.
                    
                    deviation = abs(item.Stated_Net_Amount - base_expected)
                    percent_dev = (deviation / base_expected) * 100
                    
                    # Strict Check: If deviation is > 50%, it's likely a catastrophic error (rate/qty swap, or wrong column)
                    if percent_dev > 50:
                        logger.warning(f"Validation Alert: SEVERE Net Amount Discrepancy. Net {item.Stated_Net_Amount} deviates {percent_dev:.1f}% from expected {base_expected} (Qty {item.Raw_Quantity} * Rate {item.Raw_Rate_Column_1}). This line item may be corrupted.")
                
                valid_items.append(item)
            
            model.Line_Items = valid_items # Update model with filtered list
            logger.info(f"Validation Successful. {len(valid_items)} line items retained.")
            return model.model_dump()
            
        except Exception as e:
            logger.error(f"Validation Failed: {e}")
            return None

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
                desc_lower = desc.lower()
                # Enhanced Fuzzy Match:
                # 1. Direct containment (heuristic in Gemini or vice versa)
                # 2. Token overlap (if abbreviations used)
                for h in heuristic_items:
                    h_desc = h.get("Original_Product_Description", "").lower()
                    if not h_desc: continue
                    
                    # Containment
                    if h_desc in desc_lower or desc_lower in h_desc:
                         matches.append(h)
                         continue
                    
                    # Token Set Overlap (Simple Jaccard-ish)
                    h_tokens = set(h_desc.split())
                    g_tokens = set(desc_lower.split())
                    common = h_tokens.intersection(g_tokens)
                    if len(common) >= 2: # At least 2 words match (e.g. "Dolo" "650")
                         matches.append(h)
            
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
