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
    # 0. Get Vendor Strategy (if any)
    # Refactor: We pulled strategy in calculate_cost_price loop, but cleaner to do it here or split. 
    # Let's simple reload or modify calculate_cost_price to return strategy? 
    # Or just re-scan here (inefficient but safe). 
    normalized_supplier = supplier_name.lower()
    vendors = VENDOR_RULES.get("vendors", {})


    # 1. Calculate Cost Price (CP)
    # Note: calculate_cost_price only returns float now. 
    cp_per_unit = calculate_cost_price(raw_item, supplier_name)
    
    # 2. Parse Quantities and Percents
    qty = parse_float(raw_item.Raw_Quantity)
    stated_net_amount = parse_float(raw_item.Stated_Net_Amount)
    raw_taxable_value = parse_float(raw_item.Raw_Taxable_Value) 
    
    # Discounts
    raw_disc_amount = parse_float(raw_item.Raw_Discount_Amount) if raw_item.Raw_Discount_Amount else 0.0
    discount_percent = parse_float(raw_item.Raw_Discount_Percentage)
    
    # Tax - Use Effective Rate
    effective_tax_percent = get_effective_tax_rate(raw_item)
    
    is_calculated = False



    # --- LOGIC PATCH: Derive Missing Rate ---
    # If the Extractor found no Unit Rate, we try to reverse-engineer it.
    if cp_per_unit == 0.0 and qty > 0:
        # Source 1: Taxable Value (Preferred)
        if raw_taxable_value > 0:
            derived_rate = round(raw_taxable_value / qty, 2)
            print(f"DERIVED RATE (from Taxable): {derived_rate}")
            cp_per_unit = derived_rate
            
        # Source 2: Stated Net Amount (Fallback - Must Back-Calculate Tax)
        elif stated_net_amount > 0:
            # We assume Stated Net is Inclusive of Tax
            tax_factor = 1 + (effective_tax_percent / 100.0)
            derived_taxable = stated_net_amount / tax_factor
            derived_rate = round(derived_taxable / qty, 2)
            print(f"DERIVED RATE (from Net): {derived_rate} (Net {stated_net_amount} / TaxFactor {tax_factor})")
            cp_per_unit = derived_rate

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
    
    # 8. SAFETY NET: Double-Multiplication Guard
    final_net_amount = calculated_net
    
    # Logic: If Calculated Net is huge and roughly equals (Stated Net * Qty), 
    # then the AI extracted the "Total" into the "Rate" column.
    if qty > 1 and stated_net_amount > 0:
        implied_mistake_value = stated_net_amount * qty
        
        # Check if difference is small (allow 5% variance for rounding)
        if abs(calculated_net - implied_mistake_value) < (implied_mistake_value * 0.05):
            print(f"⚠️ SAFETY NET TRIGGERED: Double Multiplication detected for item. Reverting Rate.")
            
            # 1. Trust the Stated Net Amount as the single source of truth
            final_net_amount = stated_net_amount
            
            # 2. Reverse Engineer the Real Unit Rate (CP)
            # Formula: (Total / TaxFactor) / Qty
            tax_factor = 1 + (effective_tax_percent / 100.0)
            
            # Recalculate true values
            derived_taxable_value = round(final_net_amount / tax_factor, 2)
            cp_per_unit = round(derived_taxable_value / qty, 2)
            tax_amount = round(final_net_amount - derived_taxable_value, 2)

    # 9. Standard Reconciliation (for small rounding differences)
    elif abs(calculated_net - stated_net_amount) <= 5.0:
        final_net_amount = stated_net_amount


    return {
        "Standard_Quantity": qty,
        "Calculated_Cost_Price_Per_Unit": round(cp_per_unit, 2),
        "Discount_Amount_Currency": discount_amount,
        "Calculated_Taxable_Value": derived_taxable_value,
        "Calculated_Tax_Amount": tax_amount,
        "Net_Line_Amount": final_net_amount,
        "Raw_GST_Percentage": effective_tax_percent, # Return the EFFECTIVE consolidated rate
    }

# Initialize Vector Store (Global Singleton)
try:
    from src.services.hsn_vector_store import HSNVectorStore
    # We rely on the implicit persistence path defined in the class
    GLOBAL_VECTOR_STORE = HSNVectorStore()
except Exception as e:
    print(f"Warning: HSN Vector Store unavailable: {e}")
    GLOBAL_VECTOR_STORE = None

# ... (Existing imports remain at top, this block goes after them or uses global var)

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

    # 3.5. Regex Fallback: If Batch is UNKNOWN, hunt in Description
    if batch_no == "UNKNOWN" or not batch_no:
        # Look for alphanumeric tokens like 'B2G2', 'GLP12' (Must have digits and letters)
        # Exclude common tokens: '10GM', '5ML', 'STRIPS', 'NO'
        desc_text = raw_item.Original_Product_Description
        # Tokenize
        tokens = re.findall(r'\b[A-Z0-9-]{3,10}\b', desc_text.upper())
        for t in tokens:
            if re.search(r'\d', t) and re.search(r'[A-Z]', t):
                # Has both letters and numbers
                if not re.search(r'(GM|ML|KG|PCS|TAB|CAP|SFT|RTM)', t):
                     batch_no = t
                     # Clean it from description? Optional.
                     break

        
    # 4. Clean & Enrich HSN Code
    raw_hsn = raw_item.Raw_HSN_Code
    
    # Basic cleaning: Remove letters/spaces (e.g. "3004 90" -> "300490")
    clean_ocr_hsn = re.sub(r'[^\d.]', '', str(raw_hsn)) if raw_hsn else None
    final_hsn = None

    # Priority A: Check Bulk CSV (The "Emergency Match" - Exact)
    # We look up the product description in your Master CSV
    lookup_key = raw_item.Original_Product_Description.strip().lower()
    
    if lookup_key in BULK_HSN_MAP:
        final_hsn = BULK_HSN_MAP[lookup_key]
        
    # Priority B: Vector Search (Semantic Fallback)
    elif GLOBAL_VECTOR_STORE and not final_hsn:
        # Use Description to find best HSN match
        # Lower threshold (0.5) implies stricter matching
        vector_match = GLOBAL_VECTOR_STORE.search_hsn(raw_item.Original_Product_Description, threshold=0.5)
        if vector_match:
            print(f"   -> Vector Store recovered HSN: {vector_match} for {std_name}")
            final_hsn = vector_match

    # Priority C: Use OCR with "Chapter Expansion"
    # Fallback to what was printed if no DB match found
    if not final_hsn and clean_ocr_hsn:
        final_hsn = clean_ocr_hsn
    
    # NOTE: We do NOT touch tax rates based on HSN. Strict compliance.

    # 5. Merge them
    return {
        **financials,
        "Standard_Item_Name": std_name,
        "Pack_Size_Description": pack_size,
        "Batch_No": batch_no,
        "HSN_Code": final_hsn,
        # ADD THIS LINE:
        "MRP": parse_float(raw_item.Raw_Rate_Column_2) # Maps secondary rate to MRP
    }

def distribute_global_modifiers(
    normalized_items: list[Dict[str, Any]], 
    global_discount: float, 
    freight: float
) -> list[Dict[str, Any]]:
    """
    Distributes Global Discount and Freight across line items based on their Taxable Value.
    Updates 'Net_Line_Amount' and adds 'Prorated_Global_Discount'.
    """
    # 1. Calculate Total Taxable Value
    total_taxable = sum(item.get("Calculated_Taxable_Value", 0.0) for item in normalized_items)
    
    if total_taxable == 0.0:
        return normalized_items

    # 2. Distribute Modifiers
    for item in normalized_items:
        item_taxable = item.get("Calculated_Taxable_Value", 0.0)
        weight = item_taxable / total_taxable
        
        # Calculate Share
        discount_share = round(global_discount * weight, 2)
        freight_share = round(freight * weight, 2)
        
        # Update Net Amount
        # Net = Net - Discount + Freight
        current_net = item.get("Net_Line_Amount", 0.0)
        new_net = round(current_net - discount_share + freight_share, 2)
        
        item["Net_Line_Amount"] = new_net
        item["Prorated_Global_Discount"] = discount_share
        
        # Optional: We could also track Prorated_Freight if schema allowed
        
    return normalized_items
