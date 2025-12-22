import re
from typing import Tuple, Union, Dict
from src.utils.config_loader import load_product_catalog, load_vendor_rules

# Load mappings and rules at module level
def load_and_transform_catalog() -> Dict[str, Tuple[str, str]]:
    catalog_list = load_product_catalog()
    mapping = {}
    for item in catalog_list:
        known_name = item.get("known_name")
        pack_size = item.get("standard_pack")
        if known_name:
            mapping[known_name] = (known_name, pack_size)
        for synonym in item.get("synonyms", []):
            mapping[synonym] = (known_name, pack_size)
    return mapping

PRODUCT_MAPPING = load_and_transform_catalog()
VENDOR_RULES = load_vendor_rules()

def standardize_product(raw_desc: str) -> Tuple[str, Union[str, None]]:
    """
    Matches raw description against the loaded product catalog.
    Returns (Standard Name, Pack Size).
    """
    if not raw_desc:
        return "Unknown", None
        
    key = str(raw_desc).lower().strip()
    key = re.sub(r'\s+', ' ', key)
    
    if key in PRODUCT_MAPPING:
        return PRODUCT_MAPPING[key]
        
    return str(raw_desc).strip(), None

def refine_extracted_fields(raw_item: Dict) -> Dict:
    """
    Applies strict Regex rules to clean specific fields (Qty split, HSN/Batch enforcement).
    """
    # 1. Pack Size Separation
    raw_qty = str(raw_item.get("Qty", "")).strip()
    raw_pack = str(raw_item.get("Pack", "")).strip()
    
    if raw_qty and not raw_pack:
        match = re.match(r"^(\d+)\s*([a-zA-Z*xX]+[\d]*.*)$", raw_qty)
        if match:
            raw_item["Qty"] = match.group(1)
            raw_item["Pack"] = match.group(2)

    # 2. HSN Enforcement
    raw_hsn = str(raw_item.get("HSN", "")).strip()
    if raw_hsn:
        clean_hsn = re.sub(r"[^\d]", "", raw_hsn)
        if 4 <= len(clean_hsn) <= 8:
            raw_item["HSN"] = clean_hsn
        else:
            if len(clean_hsn) < 4 or len(clean_hsn) > 8:
                 raw_item["Raw_HSN_Code"] = None
            else:
                 raw_item["Raw_HSN_Code"] = clean_hsn

    # 3. Date Normalization (Batch Cleanup)
    batch_val = str(raw_item.get("Batch", "")).strip()
    if batch_val:
        date_pattern = r"(\d{1,2}[/-]\d{2,4})" 
        date_match = re.search(date_pattern, batch_val)
        
        if date_match:
            extracted_date = date_match.group(1)
            if not raw_item.get("Expiry"):
                raw_item["Expiry"] = extracted_date
                
            clean_batch = re.sub(date_pattern, "", batch_val).strip()
            clean_batch = re.sub(r"^[\W_]+|[\W_]+$", "", clean_batch)
            raw_item["Batch"] = clean_batch if clean_batch else None

    return raw_item
