import re
from typing import Dict, Union

from .text import refine_extracted_fields, standardize_product, parse_pack_size, BULK_HSN_MAP
from .financials import parse_float, parse_quantity, reconcile_financials
from .hsn import search_hsn_neo4j

# Re-export key functions
__all__ = ['normalize_line_item', 'reconcile_financials', 'parse_float', 'parse_quantity']

def normalize_line_item(raw_item: dict, supplier_name: str = "") -> dict:
    """
    Standardizes Text ONLY. Does NOT calculate financials.
    Financials are handled by the Solver Node.
    """
    # 0. STRICT PATTERN ENFORCEMENT (The Librarian)
    raw_item = refine_extracted_fields(raw_item)

    # 1. Standardize Name
    raw_desc = raw_item.get("Product", "")
    std_name, pack_size = standardize_product(raw_desc)
    
    # If Regex extracted a pack size, prioritize it over catalog default
    regex_pack = raw_item.get("Pack")
    if regex_pack:
        pack_size = regex_pack 

    # 2. Clean Batch
    batch_no = raw_item.get("Batch", "UNKNOWN")
    if batch_no and batch_no != "UNKNOWN":
        # Remove common OCR noise prefixes
        batch_no = re.sub(r'^(OTSI |MICR |MHN- )', '', batch_no)
        # Remove numeric prefixes with pipes (e.g. "215 | ")
        batch_no = re.sub(r'^\d+\s*\|\s*', '', batch_no)

    # 3. Clean HSN
    raw_hsn = raw_item.get("HSN")
    final_hsn = None
    
    # Priority A: Check Bulk CSV
    lookup_key = raw_desc.strip().lower()
    if lookup_key in BULK_HSN_MAP:
        final_hsn = BULK_HSN_MAP[lookup_key]
        
    # Priority B: OCR Fallback (Prioritize Document Evidence)
    if not final_hsn and raw_hsn:
         clean_ocr_hsn = re.sub(r'[^\d.]', '', str(raw_hsn))
         if clean_ocr_hsn:
             final_hsn = clean_ocr_hsn

    # Priority C: Vector Search (Neo4j) - Only if no HSN found
    if not final_hsn:
        vector_match = search_hsn_neo4j(raw_desc, threshold=0.85)
        if vector_match:
            final_hsn = vector_match
             
    # Calculate Standard Quantity using Billed + Free
    # Re-using parse_quantity but storing specific breakdown
    billed_qty_val = parse_quantity(raw_item.get("Qty"), 0)
    free_qty_val = parse_quantity(raw_item.get("Free"), 0)
    
    # If "10+2" style was in Qty, parse_quantity might have handled it if passed single string?
    # Let's rely on parse_quantity implementation in financials.py which sums them if "+" exists.
    # But here we want separate fields.
    
    # Let's rely on standard_qty which sums them up.
    std_qty = parse_quantity(raw_item.get("Qty"), raw_item.get("Free"))
    
    # Heuristic: If std_qty > billed (and free is 0 in raw), try to deduce free?
    # Actually, mapper handles separation now.
    # If mapper put "10" in Qty and "2" in Free -> std_qty = 12. Correct.
    
    # 4. Tax Calculation
    # Check for "Raw_GST_Percentage" (from Mapper) or older "GST_Percent"
    raw_gst = parse_float(raw_item.get("Raw_GST_Percentage") or raw_item.get("GST_Percent"))
    
    net_line_amount = parse_float(raw_item.get("Amount"))
    calc_tax_amt = 0.0
    
    if raw_gst > 0 and net_line_amount > 0:
        # Tax_Amount = Net - (Net / (1 + Rate/100))
        # This assumes Net Amount is Inclusive of Tax
        base_amount = net_line_amount / (1 + (raw_gst / 100))
        calc_tax_amt = round(net_line_amount - base_amount, 2)

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
        "Free_Quantity": free_qty_val, # New Field
        "Net_Line_Amount": net_line_amount,
        
        # Calculate Unit Cost (Amount / Total Qty) to reflect "Scheme" benefit
        # CRITICAL FIX: The customer pays 'Amount' but receives 'Standard_Quantity' (Billed + Free)
        # So Unit Cost = Net Amount / (Billed + Free)
        "Final_Unit_Cost": (net_line_amount / (std_qty or 1.0)) if std_qty > 0 else 0.0,
        "Logic_Note": f"Qty: {billed_qty_val}+{free_qty_val}={std_qty} (Scheme Applied)",
        
        # Metadata Populated
        "MRP": raw_item.get("MRP"),
        "Rate": (net_line_amount / (std_qty or 1.0)) if std_qty > 0 else raw_item.get("Rate"),
        
        # Tax Fields
        "Raw_GST_Percentage": raw_gst,
        # For compatibility, we map this to standard fields if useful
        "SGST_Percent": raw_gst / 2 if raw_gst > 0 else 0, # Rough heuristic if not specified
        "CGST_Percent": raw_gst / 2 if raw_gst > 0 else 0,
        "Calculated_Tax_Amount": calc_tax_amt,
        
        # Validate Expiry: If it looks like an HSN (6-8 digits, no separators), clear it.
        "Expiry_Date": (
            raw_item.get("Expiry") 
            if raw_item.get("Expiry") and re.search(r'[/\-.]', str(raw_item.get("Expiry"))) # Must have separator
            and not re.match(r'^\d{6,8}$', str(raw_item.get("Expiry")).replace(" ", "")) # Must not be pure 8-digit HSN
            else None
        )
    }
