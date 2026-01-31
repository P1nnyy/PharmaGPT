import re
from typing import Dict, Tuple, Union, Any
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
PRODUCT_MAPPING = load_and_transform_catalog()
VENDOR_RULES = load_vendor_rules()

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
            raw_item["HSN"] = None
            raw_item["Raw_HSN_Code"] = clean_hsn if clean_hsn else None

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

    # 4. Smart Hierarchy Detection (The Fix C)
    struct_pack = structure_packaging_hierarchy(raw_item.get("Pack") or raw_item.get("Qty"))
    if struct_pack:
        raw_item["Analyzed_Base_Unit"] = struct_pack.get("base_unit") 
        raw_item["Analyzed_Primary_Pack"] = struct_pack.get("primary_pack_size")
        if struct_pack.get("secondary_pack_size"):
            raw_item["Analyzed_Secondary_Pack"] = struct_pack.get("secondary_pack_size")

    return raw_item

def parse_pack_size(pack_str: str) -> Dict[str, Union[str, int]]:
    """
    Parses a pack size string into structured components.
    Example: "10 T" -> {unit: "Tablet", pack: "1x10"}
    Example: "15 S" -> {unit: "Strip", pack: "1x15"}
    """
    if not pack_str:
        return {"unit": "Unit", "pack": "1x1"}
        
    s = pack_str.strip().lower()
    
    # Logic 1: "10 S", "10s", "10 T", "10 strips"
    # Matches <digits><optional space><suffix>
    match = re.search(r'(\d+)\s*([a-z]+)', s)
    if match:
        qty = match.group(1)
        suffix = match.group(2)
        
        unit = "Unit"
        if suffix in ['s', 'str', 'strip', 'strips']: unit = "Strip"
        elif suffix in ['t', 'tab', 'tabs', 'tablet', 'tablets']: unit = "Tablet"
        elif suffix in ['c', 'cap', 'caps', 'capsule', 'capsules']: unit = "Capsule"
        elif suffix in ['v', 'vial', 'vials']: unit = "Vial"
        elif suffix in ['a', 'amp', 'ampoule', 'ampoules']: unit = "Ampoule"
        elif suffix in ['b', 'bot', 'bottle', 'bottles']: unit = "Bottle"
        
        if unit == "Unit" and suffix not in ['s']: 
             # If suffix matches nothing known, return original (e.g. 15GM)
             return {"unit": "Unit", "pack": pack_str}

        return {"unit": unit, "pack": f"1x{qty}"}
        
    # Default Fallback
    return {"unit": "Unit", "pack": pack_str}

def structure_packaging_hierarchy(pack_string: str) -> Dict[str, Any]:
    """
    Parses a raw packaging string (e.g. '100ML', '10x10', '15s') into structured components.
    
    Fix C Rules:
    1. Liquid/Cream: '100ML', '50GM', '1L' -> primary=1, base='Bottle'/'Tube'.
    2. Tablet: '10x10', '15s', '10`s' -> primary=extracted, base='Tablet'.
    """
    if not pack_string:
        return None
        
    s = str(pack_string).strip().upper()
    
    # Rule 1: Liquid/Cream/Ointment Detection
    # Look for suffixes: ML, L, GM, G, OZ
    if re.search(r'\d+\s*(ML|GM|L|G|OZ)\b', s):
        # It's a volume/weight based item (Syrup, Cream, Gel)
        # return primary_pack_size = 1 (Sold as 1 Bottle/Tube)
        base_unit = 'Bottle'
        if 'GM' in s or 'G' in s:
            base_unit = 'Tube' # or Jar
            
        return {
            "primary_pack_size": 1,
            "base_unit": base_unit,
            "type": "LIQUID_WEIGHT"
        }
        
    # Rule 2: Tablet/Capsule Detection
    # Pattern A: '10x10', '5x15' (Box logic, but usually means Total Tablets? or Strips per box?)
    # Context: Usually invoices say "10x10" meaning 1 Box contains 10 Strips of 10.
    # But financial line item usually refers to the Box or the Strip?
    # If standard logic says "15s" -> 1 Strip of 15.
    
    # Pattern: '15s', '10`s', '10 s', '15 TAB'
    match_strip = re.search(r'(\d+)\s*[\'`]?s\b|(\d+)\s*TAB', s, re.IGNORECASE)
    if match_strip:
        qty = int(match_strip.group(1) or match_strip.group(2))
        return {
            "primary_pack_size": qty,
            "base_unit": 'Tablet',
            "type": "TABLET_STRIP"
        }
        
    # Pattern: '10x10'
    # This is ambiguous. It could mean "10 Strips of 10".
    # If the user buys 1 "10x10", they are buying 1 Box.
    # Total Base Units = 100.
    # Primary Pack (Strip) = 10. Secondary (Box) = 10 strips.
    # For now, let's extract the "Strip Size" if possible. 
    # Usually the second number is the strip size? OR the first? 
    # "10x10" -> 10 strips of 10. 
    # Let's assume the second number is the Primary Pack Size (Tabs per strip).
    match_box = re.search(r'(\d+)\s*[xX]\s*(\d+)', s)
    if match_box:
        outer = int(match_box.group(1))
        inner = int(match_box.group(2))
        return {
            "primary_pack_size": inner,
            "secondary_pack_size": outer, # Extract explicit Outer Pack
            "base_unit": 'Tablet',
            "type": "TABLET_BOX"
        }

    return None
