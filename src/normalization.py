import re
from typing import Union, Tuple, Dict, Any
from src.schemas import RawLineItem

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
    if "+" in cleaned_value:
        try:
            parts = cleaned_value.split('+')
            # Extract numbers from parts and sum them
            total = sum(float(re.search(r'\d+(\.\d+)?', p).group()) for p in parts if re.search(r'\d+', p))
            return total
        except:
            pass # Fallback to standard regex if math fails
    
    match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
    if match:
        return float(match.group())
    return 0.0

def get_effective_tax_rate(raw_item: RawLineItem) -> float:
    """
    Determines the single effective GST percentage for calculations.
    Priority:
    1. Raw_GST_Percentage (if explicitly combined)
    2. Raw_IGST_Percentage (if interstate)
    3. Sum of Raw_CGST_Percentage + Raw_SGST_Percentage (if split)
    """
    # 1. Check for explicit combined GST
    gst_val = parse_float(raw_item.Raw_GST_Percentage)
    if gst_val > 0:
        return gst_val
        
    # 2. Check for IGST
    igst_val = parse_float(raw_item.Raw_IGST_Percentage)
    if igst_val > 0:
        return igst_val
        
    # 3. Sum Split Taxes
    cgst_val = parse_float(raw_item.Raw_CGST_Percentage)
    sgst_val = parse_float(raw_item.Raw_SGST_Percentage)
    
    total_split_tax = cgst_val + sgst_val
    return total_split_tax

def calculate_cost_price(raw_item: RawLineItem, supplier_name: str) -> float:
    """
    Calculates the Cost Price Per Unit based on supplier-specific rules.
    """
    
    # 1. Parse inputs
    raw_qty = parse_float(raw_item.Raw_Quantity)
    
    # Check for primary rate column first, fallback to secondary if needed
    raw_rate = parse_float(raw_item.Raw_Rate_Column_1)
    if raw_rate == 0.0 and raw_item.Raw_Rate_Column_2 is not None:
         raw_rate = parse_float(raw_item.Raw_Rate_Column_2)

    # 2. Handle Zero Quantity Logic
    if raw_qty == 0.0:
        return 0.0

    # 3. Handle Supplier Specific Logic
    normalized_supplier = supplier_name.lower()
    
    # Dynamic Vendor Logic
    vendors = VENDOR_RULES.get("vendors", {})
    
    for vendor_key, rules in vendors.items():
        if vendor_key in normalized_supplier:
            calc_rules = rules.get("calculation_rules", {})
            
            # Check for Rate Divisor
            rate_divisor = calc_rules.get("rate_divisor")
            if rate_divisor:
                return raw_rate / float(rate_divisor)
    
    # Default: Standard Rate (Rate per pack/strip)
    return raw_rate

def standardize_product(raw_description: str) -> Tuple[str, str]:
    """
    Maps a raw product description to a Standard Item Name and Pack Size.
    Returns (raw_description, "Unit") if no match is found.
    """
    if raw_description in PRODUCT_MAPPING:
        return PRODUCT_MAPPING[raw_description]
    
    return (raw_description, "Unit")

def calculate_financials(raw_item: RawLineItem, supplier_name: str) -> dict:
    """
    Calculates financial figures including Cost Price, Discount Amount, Taxable Value, and Net Amount.
    Returns a dictionary corresponding to normalized fields.
    Now includes 'Discovery Mode' to identify potential vendor-specific rule deviations.
    """
    
    # 1. Calculate Cost Price (CP)
    cp_per_unit = calculate_cost_price(raw_item, supplier_name)
    
    # 2. Parse Quantities and Percents
    qty = parse_float(raw_item.Raw_Quantity)
    stated_net_amount = parse_float(raw_item.Stated_Net_Amount)
    raw_taxable_value = parse_float(raw_item.Raw_Taxable_Value) # New Field
    
    # Discounts
    raw_disc_amount = parse_float(raw_item.Raw_Discount_Amount) if raw_item.Raw_Discount_Amount else 0.0
    discount_percent = parse_float(raw_item.Raw_Discount_Percentage)
    
    # Tax - Use Effective Rate
    effective_tax_percent = get_effective_tax_rate(raw_item)

    # 3. Calculate Gross Value (Baseline)
    gross_value = qty * cp_per_unit
    
    # 4. Calculate Discount Amount (Branching Logic)
    if raw_disc_amount > 0:
        discount_amount = raw_disc_amount
    elif discount_percent > 0:
        discount_amount = round(gross_value * (discount_percent / 100.0), 2)
    else:
        discount_amount = 0.0
    
    # 5. Calculate Taxable Value (Derived)
    derived_taxable_value = round(gross_value - discount_amount, 2)
    
    # 6. Calculate Tax Amount
    tax_amount = round(derived_taxable_value * (effective_tax_percent / 100.0), 2)
    
    # 7. Calculate Total Amount (Calculated Net)
    calculated_net = round(derived_taxable_value + tax_amount, 2)
    
    # 8. Reconciliation & Discovery Mode
    diff = abs(calculated_net - stated_net_amount)
    final_net_amount = calculated_net
    
    # --- TRIANGULATION CHECK (New Logic) ---
    # Check if Stated Net Amount is actually the Taxable Value
    # Condition: 
    # 1. Stated Net is close to Derived Taxable (within 1.0)
    # 2. Calculated Net (with tax) is significantly higher than Stated Net (diff > 5.0)
    # 3. Tax is present (>0)
    
    might_be_taxable = abs(stated_net_amount - derived_taxable_value) < 1.0
    significant_tax_impact = abs(calculated_net - stated_net_amount) > 5.0
    
    if might_be_taxable and significant_tax_impact and effective_tax_percent > 0:
        print(f"Correction Triggered for {supplier_name}: Extracted Net ({stated_net_amount}) matches Taxable Value. Overriding with Calculated Net ({calculated_net}).")
        # In this specific case, we TRUST our calculation (which adds tax) over the Stated Net (which excluded it)
        final_net_amount = calculated_net
        
    elif diff <= 5.0:
        # Acceptable variance
        if diff <= 0.05:
            final_net_amount = stated_net_amount
    else:
        # --- DISCOVERY MODE TRIGGERED ---
        # The numbers don't add up. Let's try to reverse-engineer why.
        print(f"Discovery Mode Triggered for {supplier_name} - Item: {raw_item.Original_Product_Description} (Calc: {calculated_net}, Stated: {stated_net_amount})")
        
        # Hypothesis 1: Vendor uses 'Rate per Dozen'
        rate_doz_net = calculated_net / 12.0
        if abs(rate_doz_net - stated_net_amount) < 1.0:
            print(f"SUGGESTION: Vendor {supplier_name} likely uses 'Rate per Dozen'. Add 'rate_divisor: 12.0' to vendor_rules.yaml.")
            final_net_amount = stated_net_amount # Trust the stated amount for now
            
        # Hypothesis 2: Vendor lists 'Total Amount' in the Rate column
        elif qty > 0 and abs((calculated_net / qty) - stated_net_amount) < 5.0: 
             print(f"SUGGESTION: Vendor {supplier_name} likely lists 'Total Amount' in the Rate column.")
             final_net_amount = stated_net_amount

        # Hypothesis 3: Vendor lists 'Taxable Value' (Excluding Tax) in the Amount column
        # Check: Derived Taxable Value ~= Stated Net Amount (This is now largely handled by Triangulation above, but kept as backup/diagnostic)
        elif abs(derived_taxable_value - stated_net_amount) <= 1.0:
            print(f"SUGGESTION: Vendor {supplier_name} lists 'Taxable Value' in the Amount column. Add 'amount_excludes_tax: true' to vendor_rules.yaml.")
            final_net_amount = calculated_net

    return {
        "Standard_Quantity": qty,
        "Calculated_Cost_Price_Per_Unit": round(cp_per_unit, 2),
        "Discount_Amount_Currency": discount_amount,
        "Calculated_Taxable_Value": derived_taxable_value,
        "Calculated_Tax_Amount": tax_amount,
        "Net_Line_Amount": final_net_amount,
        "Raw_GST_Percentage": effective_tax_percent, # Return the EFFECTIVE consolidated rate
    }

def normalize_line_item(raw_item: RawLineItem, supplier_name: str) -> Dict[str, Any]:
    """
    The Master Function:
    Combines financial calculations AND product standardization to produce
    a complete dictionary ready for the NormalizedLineItem schema.
    """
    # 1. Get Financials
    financials = calculate_financials(raw_item, supplier_name)
    
    # 2. Get Standard Product Details
    std_name, pack_size = standardize_product(raw_item.Original_Product_Description)
    
    # 3. Clean Batch Number
    batch_no = raw_item.Batch_No
    if batch_no is None or not batch_no.strip():
        batch_no = "UNKNOWN"
    else:
        # Remove common OCR noise prefixes
        batch_no = re.sub(r'^(OTSI |MICR |MHN- )', '', batch_no)
        # Remove numeric prefixes with pipes (e.g. "215 | ")
        batch_no = re.sub(r'^\d+\s*\|\s*', '', batch_no)
        
    # 4. Clean & Enrich HSN Code
    raw_hsn = raw_item.Raw_HSN_Code
    
    # Basic cleaning: Remove letters/spaces (e.g. "3004 90" -> "300490")
    clean_ocr_hsn = re.sub(r'[^\d.]', '', str(raw_hsn)) if raw_hsn else None
    final_hsn = None

    # Priority A: Check Bulk CSV (The "Emergency Match")
    # We look up the product description in your Master CSV
    lookup_key = raw_item.Original_Product_Description.strip().lower()
    
    if lookup_key in BULK_HSN_MAP:
        final_hsn = BULK_HSN_MAP[lookup_key]
    
    # Priority B: Use OCR with "Chapter Expansion"
    elif clean_ocr_hsn:
        final_hsn = clean_ocr_hsn

    # 5. Merge them
    return {
        **financials,
        "Standard_Item_Name": std_name,
        "Pack_Size_Description": pack_size,
        "Batch_No": batch_no,
        "HSN_Code": final_hsn
    }
