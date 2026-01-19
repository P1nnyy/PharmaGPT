import re
from typing import List, Dict, Any, Tuple, Union
from src.domain.schemas import NormalizedLineItem


from src.utils.config_loader import load_product_catalog, load_vendor_rules, load_hsn_master

# Load the CSV map once when the module starts
BULK_HSN_MAP = load_hsn_master()

def load_and_transform_catalog() -> Dict[str, Tuple[str, str]]:
    """
    Loads the product catalog from YAML and transforms it into a dictionary
    mapping known names and synonyms to (Standard Name, Pack Size).
    """
    catalog_list = load_product_catalog()
    mapping = {}
    
    for item in catalog_list:
        known_name = item.get("known_name")
        pack_size = item.get("standard_pack")
        
        # Self-mapping
        if known_name:
            mapping[known_name] = (known_name, pack_size)
            
        # Synonym mapping
        for synonym in item.get("synonyms", []):
            mapping[synonym] = (known_name, pack_size)
            
    return mapping

# Load mappings and rules at module level
# Load mappings and rules at module level
PRODUCT_MAPPING = load_and_transform_catalog()
VENDOR_RULES = load_vendor_rules()

from src.services.embeddings import generate_embedding
from neo4j import GraphDatabase
import os

# Neo4j Config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_DRIVER = None

def get_hsn_driver():
    global _DRIVER
    if _DRIVER is None:
        try:
            _DRIVER = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            _DRIVER.verify_connectivity()
        except Exception as e:
            print(f"HSN Search: DB Connection Failed: {e}")
            return None
    return _DRIVER

def search_hsn_neo4j(description: str, threshold: float = 0.85) -> str:
    """
    Searches for HSN code in Neo4j using vector similarity.
    Assumes (:HSN) nodes have a 'description' and 'embedding' property.
    And a vector index named 'hsn_vector_index'.
    """
    if not description:
        return None
        
    driver = get_hsn_driver()
    if not driver:
        return None
        
    try:
        embedding = generate_embedding(description)
        if not embedding:
            return None
            
        # Query for nearest neighbor
        query = """
        CALL db.index.vector.queryNodes('hsn_vector_index', 1, $embedding)
        YIELD node, score
        WHERE score > $threshold
        RETURN node.code as hsn_code
        """
        
        with driver.session() as session:
            result = session.run(query, embedding=embedding, threshold=threshold).single()
            if result:
                return result["hsn_code"]
    except Exception as e:
        # Fails silently to allow fallback to OCR
        # print(f"HSN Vector Search Error: {e}")
        pass
        
    return None

def parse_float(value: Union[str, float, None]) -> float:
    """
    Parses a float from a string or float value, handling common currency symbols and formatting.
    Returns 0.0 if value is None or cannot be parsed.
    """
    if value is None:
        return 0.0
    if isinstance(value, (float, int)):
        return float(value)
    
    # Remove common currency symbols and whitespace
    # Also ignore "Rs", "Rs.", "INR", "$"
    cleaned_value = str(value).strip().lower()
    cleaned_value = re.sub(r'(?:rs\.?|inr|\$|€|£)', '', cleaned_value).strip()
    # Remove commas
    cleaned_value = cleaned_value.replace(',', '')

    # Check for presence of alphabetic characters (indicating text description)
    # But allow "kg", "g", "ml" ? User said "fail if the string is primarily text description".
    # Dolo 650 -> "d o l o 6 5 0". Has letters.
    # 10 kg -> "1 0 k g". Has letters.
    # If we strictly fail on ANY letters, we might lose units.
    # But often OCR puts "10kg" in quantity column?
    # Let's try: if match is found, check if the remaining string has too many letters.
    # Or simpler: if it STARTS with a letter?
    # "Dolo 650" starts with D.
    # "Batch 2024" starts with B.
    # "10 kg" starts with 1.
    
    if not cleaned_value:
        return 0.0
        


    # Extract the first valid number found (handling potential text around it)
    # Handle "Billed + Free" formats (e.g. "10+2", "4.50+.50")
    # Rule: The first number is usually the Billed Quantity. The second is Free.
    # We should return ONLY the Billed Quantity for financial calculations.
    if "+" in cleaned_value:
        try:
            parts = cleaned_value.split('+')
            # Extract the FIRST number found (Billed Qty)
            first_part = parts[0]
            match = re.search(r'\d+(\.\d+)?', first_part)
            if match:
                return float(match.group())
        except:
            pass # Fallback to standard regex if match fails
    
    match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
    if match:
        return float(match.group())
    return 0.0

def standardize_product(raw_desc: str) -> Tuple[str, Union[str, None]]:
    """
    Matches raw description against the loaded product catalog.
    Returns (Standard Name, Pack Size) if found.
    Otherwise returns (Raw Description, None).
    """
    if not raw_desc:
        return "Unknown", None
        
    # Normalize: lower, strip, remove extra spaces
    key = str(raw_desc).lower().strip()
    key = re.sub(r'\s+', ' ', key)
    
    # 1. Direct Match
    if key in PRODUCT_MAPPING:
        return PRODUCT_MAPPING[key]
        
    # 2. Fuzzy Match / Synonym Check (Simplified)
    # The PRODUCT_MAPPING already contains synonyms as keys (see load_and_transform_catalog)
    # So we just check if the key exists.
    
    # If no match, return original (Title Case for aesthetics)
    return str(raw_desc).strip(), None



# src/normalization.py (Cleaned Version)

def refine_extracted_fields(raw_item: Dict) -> Dict:
    """
    Applies strict Regex rules to clean specific fields.
    1. Quantity/Pack Split: "115GM" -> Qty: 1, Pack: 15GM
    2. HSN: Enforce 4-8 digits.
    """
    # 1. Pack Size Separation Strategy
    raw_qty = str(raw_item.get("Qty", "")).strip()
    raw_pack = str(raw_item.get("Pack", "")).strip()
    
    # Only split if Pack is empty and Qty looks suspicious (Digits + Text)
    if raw_qty and not raw_pack:
        # Pattern: Starts with Digits, followed by Letters/Symbols (e.g. 115GM, 1200ML, 10TAB)
        match = re.match(r"^(\d+)\s*([a-zA-Z*xX]+[\d]*.*)$", raw_qty)
        if match:
            qty_part = match.group(1)
            pack_part = match.group(2)
            
            # Heuristic: If split, update the dict
            raw_item["Qty"] = qty_part
            raw_item["Pack"] = pack_part
            # raw_item["Product"] += f" ({pack_part})" # Optional: Append back to desc? Maybe not.

    # 2. HSN Enforcement
    raw_hsn = str(raw_item.get("HSN", "")).strip()
    if raw_hsn:
        # Remove all non-digits
        clean_hsn = re.sub(r"[^\d]", "", raw_hsn)
        
        # Enforce Length (4 to 8 digits)
        if 4 <= len(clean_hsn) <= 8:
            raw_item["HSN"] = clean_hsn
        else:
            # Invalid HSN (too short/long) -> Nullify to avoid pollution
            # Or keep it if it's close? "The Strict Librarian" says enforce.
            if len(clean_hsn) > 0:
                 # Logic choice: If it's valid digits but wrong length (e.g. 3 digits), maybe keep or drop?
                 # Let's drop it if it's garbage. 
                 # But if it's 3 digit, user might want to see it? 
                 # Prompt said "Ensure ... strictly a 4-to-8 digit string".
                 if len(clean_hsn) < 4 or len(clean_hsn) > 8:
                     # Check if it was purely text trash
                     raw_item["Raw_HSN_Code"] = None
                 else:
                     raw_item["Raw_HSN_Code"] = clean_hsn
            else:
                raw_item["Raw_HSN_Code"] = None

    # 3. Date Normalization (Batch Cleanup)
    # Scan Batch for date patterns (e.g. DD/MM/YY)
    batch_val = str(raw_item.get("Batch", "")).strip()
    if batch_val:
        # Regex for dates: DD/MM/YY, DD-MM-YY, MM/YY, MM-YY
        # (Allows 2 or 4 digit year)
        date_pattern = r"(\d{1,2}[/-]\d{2,4})" 
        date_match = re.search(date_pattern, batch_val)
        
        if date_match:
            extracted_date = date_match.group(1)
            
            # Move to Expiry if Expiry is empty
            if not raw_item.get("Expiry"):
                raw_item["Expiry"] = extracted_date
                
            # Remove date from Batch to clean it
            clean_batch = re.sub(date_pattern, "", batch_val).strip()
            # Clean up trailing/leading separators like "-" or "/" or ","
            clean_batch = re.sub(r"^[\W_]+|[\W_]+$", "", clean_batch)
            
            raw_item["Batch"] = clean_batch if clean_batch else None

    return raw_item

import math

def parse_quantity(value: Union[str, float, None], free_qty: Union[str, float, None] = 0) -> int:
    """
    Parses a quantity string, handling sums (e.g. '10+2') and rounding UP to nearest integer.
    Rule: 1.86 -> 2, 1.5 -> 2.
    Rule: 1.5 + 1.5 -> 3.0 -> 3.
    """
    if value is None:
        value = 0
    if free_qty is None:
        free_qty = 0
        
    # Helper to clean and parse float
    def clean_float(val):
        if isinstance(val, (float, int)):
            return float(val)
        s = str(val).strip().lower()
        s = re.sub(r'(?:rs\.?|inr|\$|€|£|,)', '', s)
        if not s: return 0.0
        
        # Handle "10+2" inside single string
        if "+" in s:
            try:
                parts = s.split('+')
                return sum(float(re.search(r'-?\d+(\.\d+)?', p).group() or 0) for p in parts if re.search(r'-?\d+(\.\d+)?', p))
            except:
                pass
                
        match = re.search(r'-?\d+(\.\d+)?', s)
        return float(match.group()) if match else 0.0

    billed_q = clean_float(value)
    free_q = clean_float(free_qty)
    
    total_qty = billed_q + free_q
            
    return math.ceil(total_qty)

def normalize_line_item(raw_item: dict, supplier_name: str = "") -> dict: # Note: Input is now dict from Harvester
    """
    Standardizes Text ONLY. Does NOT calculate financials.
    Financials are handled by the Solver Node.
    """
    # 0. STRICT PATTERN ENFORCEMENT (The Librarian)
    raw_item = refine_extracted_fields(raw_item)

    # 1. Standardize Name
    raw_desc = raw_item.get("Product", "")
    std_name, pack_size = standardize_product(raw_desc)
    
    # If Regex extracted a pack size, prioritize it over catalog default?
    # Or merge?
    regex_pack = raw_item.get("Pack")
    if regex_pack:
        pack_size = regex_pack # Override catalog default with actual observed pack

    # 2. Clean Batch
    batch_no = raw_item.get("Batch", "UNKNOWN")
    if batch_no and batch_no != "UNKNOWN":
        # Remove common OCR noise prefixes
        batch_no = re.sub(r'^(OTSI |MICR |MHN- )', '', batch_no)
        # Remove numeric prefixes with pipes (e.g. "215 | ")
        batch_no = re.sub(r'^\d+\s*\|\s*', '', batch_no)

    # 3. Clean HSN (Keep your existing HSN logic)
    raw_hsn = raw_item.get("HSN")
    final_hsn = None
    
    # Priority A: Check Bulk CSV
    lookup_key = raw_desc.strip().lower()
    if lookup_key in BULK_HSN_MAP:
        final_hsn = BULK_HSN_MAP[lookup_key]
        
    # Priority B: Vector Search (Neo4j)
    elif not final_hsn:
        # Use our new Neo4j search function
        vector_match = search_hsn_neo4j(raw_desc, threshold=0.80)
        if vector_match:
            final_hsn = vector_match
            
    # Priority C: OCR Fallback
    if not final_hsn and raw_hsn:
         clean_ocr_hsn = re.sub(r'[^\d.]', '', str(raw_hsn))
         if clean_ocr_hsn:
             final_hsn = clean_ocr_hsn
             
    # Calculate Standard Quantity using Billed + Free
    std_qty = parse_quantity(raw_item.get("Qty"), raw_item.get("Free"))

    return {
        "Standard_Item_Name": std_name,
        "Pack_Size_Description": pack_size,
        "Batch_No": batch_no,
        "HSN_Code": final_hsn,
        # PASS THROUGH RAW NUMBERS FOR THE SOLVER
        "Raw_Quantity": raw_item.get("Qty"),
        "Raw_Free": raw_item.get("Free"),
        "Invoice_Line_Amount": raw_item.get("Amount"),
        "Raw_MRP": raw_item.get("MRP"),
        
        # REQUIRED FOR FRONTEND / SERVER SCHEMA
        "Standard_Quantity": std_qty,
        "Net_Line_Amount": parse_float(raw_item.get("Amount")), 
        
        # Calculate Unit Cost (Amount / Qty) as placeholder until Solver
        # CRITICAL FIX: TRUST AMOUNT / QTY over Extracted Rate (which might be MRP)
        "Final_Unit_Cost": (parse_float(raw_item.get("Amount")) / (std_qty or 1.0)) if std_qty > 0 else 0.0,
        "Logic_Note": "Pre-Solver Extraction",
        
        # Metadata Populated
        "MRP": raw_item.get("MRP"),
        "Rate": (parse_float(raw_item.get("Amount")) / (std_qty or 1.0)) if std_qty > 0 else raw_item.get("Rate"),
        # Validate Expiry: If it looks like an HSN (6-8 digits, no separators), clear it.
        "Expiry_Date": (
            raw_item.get("Expiry") 
            if raw_item.get("Expiry") and re.search(r'[/\-.]', str(raw_item.get("Expiry"))) # Must have separator
            and not re.match(r'^\d{6,8}$', str(raw_item.get("Expiry")).replace(" ", "")) # Must not be pure 8-digit HSN
            else None
        )
    }

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> list:
    """
    SMART DIRECTIONAL RECONCILIATION:
    Adjusts line items to match Grand Total based on mathematical directionality.
    
    Logic:
    1. Calc Current Sum.
    2. Calc Gap = Current Sum - Grand Total.
    3. If Gap > 0 (Inflation): We need to SUBTRACT. Look for Discounts. IGNORE Tax/Freight.
    4. If Gap < 0 (Deflation): We need to ADD. Look for Tax/Freight. IGNORE Discounts.
    5. Distribute the chosen modifier pro-rata.
    """
    if not line_items or grand_total <= 0:
        return line_items
        
    current_sum = sum(float(item.get("Net_Line_Amount", 0)) for item in line_items)
    gap = current_sum - grand_total
    
    # User Requirement: ALWAYS adjust to match Grand Total.
    # Removed threshold check (previous logic skipped if gap < 0.5%)

    import logging
    logger = logging.getLogger("normalization")
    
    if abs(gap) < 0.01:
        # Truly negligible
        return line_items

    logger.info(f"Reconcile: GAP DETECTED. Sum {current_sum:.2f} vs Total {grand_total:.2f} (Gap {gap:.2f})")
    
    # Initialize
    modifier_to_apply = -gap # We always want to negate the gap
    action = "FORCED_MATCH"
    
    # Attempt to label the action based on available headers (for better UX)
    # But strictly perform the math regardless.
    
    # Extract Modifiers for labeling
    g_disc = abs(float(global_modifiers.get("Global_Discount_Amount", 0) or 0))
    g_tax = abs(float(global_modifiers.get("Global_Tax_Amount", 0) or 0) + 
                float(global_modifiers.get("SGST_Amount", 0) or 0) + 
                float(global_modifiers.get("CGST_Amount", 0) or 0) + 
                float(global_modifiers.get("IGST_Amount", 0) or 0))
    
    if gap > 0:
        # Inflation (Sum > Total). Reduce.
        if g_disc > 0:
            action = "APPLY_DISCOUNT_CORRECTION"
            logger.info("Reconcile: Gap attributed to Global Discount.")
        else:
            action = "IMPLICIT_REDUCTION" 
            logger.info("Reconcile: Gap treated as Implicit Reduction/Rounding.")
            
    elif gap < 0:
        # Deflation (Sum < Total). Increase.
        adder_sum = g_tax 
        if adder_sum > 0:
            action = "APPLY_TAX_CORRECTION"
            logger.info("Reconcile: Gap attributed to Global Tax.")
        else:
            action = "IMPLICIT_ADDITION"
            logger.info("Reconcile: Gap treated as Implicit Addition/Rounding.")

    # EXECUTE DISTRIBUTION
    if modifier_to_apply != 0:
        for item in line_items:
            original_net = float(item.get("Net_Line_Amount", 0))
            ratio = original_net / current_sum if current_sum > 0 else 0
            
            share = modifier_to_apply * ratio
            new_net = original_net + share # Add (modifier might be negative)
            
            # Metadata for UI Feedback "Perfect Match"
            correction_factor = new_net / original_net if original_net != 0 else 1.0
            
            item["Net_Line_Amount"] = round(new_net, 2)
            item["Is_Calculated"] = True # New Flag for Frontend UI (Calculator Icon)
            
            # Recalculate Unit Cost
            qty = float(item.get("Standard_Quantity", 1) or 1)
            if qty > 0:
                item["Final_Unit_Cost"] = round(new_net / qty, 2)
            
            # logic_note update
            factor_str = f"{correction_factor:.4f}x"
            # Append specific note
            old_note = item.get("Logic_Note", "")
            item["Logic_Note"] = f"{old_note} [Reconcile: {action}, Factor: {factor_str}]"

    return line_items
