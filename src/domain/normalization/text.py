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
    Standardizes a product description by first extracting trailing packaging notations
    using regex (Regex-First), then matching the cleaned name against the product catalog (Mapping-Second).
    Returns (Standard Name, Pack Size) if found or extracted.
    Otherwise returns (Raw Description, None).
    """
    if not raw_desc:
        return "Unknown", None
        
    original_desc = str(raw_desc).strip()
    
    # 1. Regex-First: Extract trailing pack sizes
    # Matches patterns like '10x15', '1x6', '10's', '15s', '10 Tabs', '15 Caps', '10 T', '15 C' at the end of the string
    pack_match = re.search(r'\s+((?:\d+\s*[xX]\s*\d+)|\d+\s*[\'`]?s\b|\d+\s*(?:TAB|CAP|T|C|STRIP)S?\b)$', original_desc, re.IGNORECASE)
    
    extracted_pack = None
    clean_name = original_desc
    
    if pack_match:
        extracted_pack = pack_match.group(1).strip()
        # Remove the pack size from the end of the name
        clean_name = original_desc[:pack_match.start()].strip()
    
    # Normalize clean_name for dictionary lookup: lower, strip, remove extra spaces
    key = clean_name.lower()
    key = re.sub(r'\s+', ' ', key)
    
    # 2. Mapping-Second: Direct Match or Synonym Check
    if key in PRODUCT_MAPPING:
        std_name, cat_pack = PRODUCT_MAPPING[key]
        # Prefer the newly extracted pack from the string, fallback to catalog pack
        return std_name, extracted_pack if extracted_pack else cat_pack
        
    # If no match in mapping, return the cleaned Title Case original with the extracted pack
    # Title Case for aesthetics but preserving the parsed info
    return clean_name.title() if clean_name.islower() or clean_name.isupper() else clean_name, extracted_pack

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
    Legacy wrapper for pack size parsing. Now uses `structure_packaging_hierarchy`
    under the hood as the single source of truth for all packaging math.
    Example: "10 T" -> {"unit": "Tablet", "pack": "1x10"}
    Example: "10x15" -> {"unit": "Tablet", "pack": "10x15"}
    """
    if not pack_str:
        return {"unit": "Unit", "pack": "1x1"}
        
    s = pack_str.strip()
    struct = structure_packaging_hierarchy(s)
    
    if struct:
        base_unit = struct.get("base_unit", "Unit")
        primary = struct.get("primary_pack_size", 1)
        secondary = struct.get("secondary_pack_size", 1)
        
        # If it's a liquid or tube, keep the original string as the pack (e.g., '100ML')
        if base_unit in ['Bottle', 'Tube', 'Vial', 'Ampoule']:
            return {
                "unit": "Unit", 
                "pack": s,
                "conversion_factor": 1
            }
            
        # Reconstruct the string for tablets/capsules/strips
        if secondary > 1 or 'x' in s.lower():
            return {
                "unit": base_unit, 
                "pack": f"{secondary}x{primary}",
                "conversion_factor": secondary * primary
            }
        else:
            return {
                "unit": base_unit, 
                "pack": f"1x{primary}",
                "conversion_factor": primary
            }
            
    # Default Fallback
    return {"unit": "Unit", "pack": s, "conversion_factor": 1}

def structure_packaging_hierarchy(pack_string: str, enrichment_category: str = None) -> Union[Dict[str, Any], None]:
    """
    Parses a raw packaging string (e.g. '100ML', '10x10', '15s', '10 Tabs') into structured components.
    This acts as the single source of truth for packaging hierarchy, unit categorization, and math calculation.
    Accepts optional enrichment_category (e.g. 'Drops', 'Syrup') to override detection.
    """
    # 0. Category Override Logic (Fix for LUBIMOIST and others)
    if enrichment_category:
        cat = str(enrichment_category).strip().upper()
        
        # Liquid/Drops/Syrup -> Bottle
        if any(x in cat for x in ['DROPS', 'SYRUP', 'LIQUID', 'SOLUTION', 'SUSPENSION', 'LOTION']):
            return {
                "primary_pack_size": 1,
                "secondary_pack_size": 1,
                "total_base_units": 1,
                "conversion_factor": 1,
                "base_unit": 'Bottle',
                "type": "LIQUID_BOTTLE"
            }
            
        # Cream/Gel/Ointment -> Tube
        if any(x in cat for x in ['CREAM', 'GEL', 'OINTMENT']):
             return {
                "primary_pack_size": 1,
                "secondary_pack_size": 1,
                "total_base_units": 1,
                "conversion_factor": 1,
                "base_unit": 'Tube',
                "type": "TUBE"
            }
            
        # Injection/Vial -> Vial
        if any(x in cat for x in ['INJECTION', 'VIAL', 'AMPOULE']):
             return {
                "primary_pack_size": 1,
                "secondary_pack_size": 1,
                "total_base_units": 1,
                "conversion_factor": 1,
                "base_unit": 'Vial',
                "type": "VIAL"
            }

    if not pack_string:
        return None
        
    s = str(pack_string).strip().upper()
    
    # Rule 1: Liquid/Cream/Ointment Detection
    # Look for suffixes: ML, L, GM, G, OZ
    if re.search(r'\d+\s*(ML|GM|L|G|OZ)\b', s):
        base_unit = 'Bottle'
        if 'GM' in s or 'G' in s:
            base_unit = 'Tube'
            
        return {
            "primary_pack_size": 1,
            "secondary_pack_size": 1,
            "total_base_units": 1,
            "conversion_factor": 1,
            "base_unit": base_unit,
            "type": "LIQUID_WEIGHT"
        }
        
    # Rule 2: Tablet/Capsule/Strip Detection
    # Pattern A: '15s', '10`s', '10 s', '15 TAB', '15 CAP', '15 STRIPS', '10 T', '15 C'
    match_strip = re.search(r'^(\d+)\s*(?:[\'`]?S\b|TAB|T\b|CAP|C\b|STRIP|V\b|A\b|B\b)', s)
    if match_strip:
        qty = int(match_strip.group(1))
        unit = 'Tablet'
        if 'CAP' in s or 'C' in s.split(): unit = 'Capsule'
        elif 'V' in s.split(): unit = 'Vial'
        elif 'A' in s.split(): unit = 'Ampoule'
        elif 'B' in s.split(): unit = 'Bottle'
        
        return {
            "primary_pack_size": qty,
            "secondary_pack_size": 1,
            "total_base_units": qty,
            "conversion_factor": qty,
            "base_unit": unit,
            "type": "TABLET_STRIP" if unit in ['Tablet', 'Capsule'] else "LIQUID_UNIT"
        }
        
    # Pattern B: '10x10', '1x6', '5x15' (NxM)
    # The standard convention: Outer x Inner (e.g. 10 strips of 15 tablets -> 10x15)
    # The first number is the outer pack (Strips per box).
    # The second number is the inner pack (Tabs per strip).
    match_box = re.search(r'(\d+)\s*[xX]\s*(\d+)', s)
    if match_box:
        outer = int(match_box.group(1))
        inner = int(match_box.group(2))
        return {
            "primary_pack_size": inner,
            "secondary_pack_size": outer,
            "total_base_units": inner * outer, 
            "conversion_factor": inner * outer,
            "base_unit": 'Tablet', # Defaulting to Tablet/Capsule for NxM
            "type": "TABLET_BOX"
        }

    return None
