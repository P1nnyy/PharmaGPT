import re
from src.utils.config_loader import load_hsn_master
from src.normalization.parsers import parse_float, parse_quantity
from src.normalization.text_utils import standardize_product, refine_extracted_fields
from src.normalization.financials import reconcile_financials

BULK_HSN_MAP = load_hsn_master()

try:
    from src.services.hsn_vector_store import HSNVectorStore
    GLOBAL_VECTOR_STORE = HSNVectorStore()
except Exception as e:
    print(f"Warning: Vector Store failed to load: {e}")
    GLOBAL_VECTOR_STORE = None

def normalize_line_item(raw_item: dict, supplier_name: str = "") -> dict: 
    """
    Standardizes Text ONLY. Does NOT calculate financials.
    Financials are handled by the Solver Node.
    """
    # 0. STRICT PATTERN ENFORCEMENT
    raw_item = refine_extracted_fields(raw_item)

    # 1. Standardize Name
    raw_desc = raw_item.get("Product", "")
    std_name, pack_size = standardize_product(raw_desc)
    
    regex_pack = raw_item.get("Pack")
    if regex_pack:
        pack_size = regex_pack 

    # 2. Clean Batch
    batch_no = raw_item.get("Batch", "UNKNOWN")
    if batch_no and batch_no != "UNKNOWN":
        batch_no = re.sub(r'^(OTSI |MICR |MHN- )', '', batch_no)
        batch_no = re.sub(r'^\d+\s*\|\s*', '', batch_no)

    # 3. Clean HSN
    raw_hsn = raw_item.get("HSN")
    final_hsn = None
    
    lookup_key = raw_desc.strip().lower()
    if lookup_key in BULK_HSN_MAP:
        final_hsn = BULK_HSN_MAP[lookup_key]
    elif GLOBAL_VECTOR_STORE and not final_hsn:
        vector_match = GLOBAL_VECTOR_STORE.search_hsn(raw_desc, threshold=0.75)
        if vector_match:
            final_hsn = vector_match
            
    if not final_hsn and raw_hsn:
         clean_ocr_hsn = re.sub(r'[^\d.]', '', str(raw_hsn))
         if clean_ocr_hsn:
             final_hsn = clean_ocr_hsn

    return {
        "Standard_Item_Name": std_name,
        "Pack_Size_Description": pack_size,
        "Batch_No": batch_no,
        "HSN_Code": final_hsn,
        # PASS THROUGH RAW NUMBERS
        "Raw_Quantity": raw_item.get("Qty"),
        "Invoice_Line_Amount": raw_item.get("Amount"),
        "Raw_MRP": raw_item.get("MRP"),
        
        # REQUIRED FOR FRONTEND / SERVER SCHEMA
        "Standard_Quantity": parse_quantity(raw_item.get("Qty")),
        "Net_Line_Amount": parse_float(raw_item.get("Amount")), 
        
        "Final_Unit_Cost": (parse_float(raw_item.get("Amount")) / (parse_quantity(raw_item.get("Qty")) or 1.0)) if raw_item.get("Qty") else 0.0,
        "Logic_Note": "Pre-Solver Extraction",
        
        # Metadata Populated
        "MRP": raw_item.get("MRP"),
        "Rate": (parse_float(raw_item.get("Amount")) / (parse_quantity(raw_item.get("Qty")) or 1.0)) if raw_item.get("Qty") else raw_item.get("Rate"),
        # Validate Expiry
        "Expiry_Date": (
            raw_item.get("Expiry") 
            if raw_item.get("Expiry") and re.search(r'[/\-.]', str(raw_item.get("Expiry"))) 
            and not re.match(r'^\d{6,8}$', str(raw_item.get("Expiry")).replace(" ", "")) 
            else None
        )
    }

# Expose parse_float/parse_quantity for other consumers if needed
__all__ = ['normalize_line_item', 'reconcile_financials', 'parse_float', 'parse_quantity']
