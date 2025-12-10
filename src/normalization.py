import re
from typing import Union, Tuple, Dict, Any
from src.schemas import RawLineItem

PRODUCT_MAPPING = {
    # Antibiotics
    "Product A": ("Standard Product A", "10 strips"),
    "Product B": ("Standard Product B", "1x1"),
    "Augmentin 625": ("Augmentin 625 Duo", "10 tabs"),
    "Augmentin Duo": ("Augmentin 625 Duo", "10 tabs"),
    "Amoxyclav 625": ("Augmentin 625 Duo", "10 tabs"),
    "Azithral 500": ("Azithral 500mg Tablet", "5 tabs"),
    "Cipcal 500": ("Cipcal 500mg Window", "10 tabs"),
    
    # Pain & Fever
    "Dolo 650": ("Dolo 650mg Tablet", "15 tabs"),
    "Dolo": ("Dolo 650mg Tablet", "15 tabs"),
    "Crocin 650": ("Crocin 650mg Advance", "15 tabs"),
    "Calpol 500": ("Calpol 500mg Tablet", "15 tabs"),
    "Combiflam": ("Combiflam Tablet", "20 tabs"),
    
    # Gastric
    "Pan 40": ("Pan 40mg Tablet", "15 tabs"),
    "Pan D": ("Pan D Capsule", "15 caps"),
    "Rantac 150": ("Rantac 150mg Tablet", "30 tabs"),
    "Omez": ("Omez 20mg Capsule", "20 caps"),
    
    # Vitamins
    "Becosules": ("Becosules Capsule", "20 caps"),
    "Limcee": ("Limcee 500mg Tablet", "15 tabs"),
    "Shelcal 500": ("Shelcal 500mg Tablet", "15 tabs"),
    
    # Chronic
    "Telma 40": ("Telma 40mg Tablet", "15 tabs"),
    "Telma H": ("Telma H Tablet", "15 tabs"),
    "Amlong 5": ("Amlong 5mg Tablet", "15 tabs"),
    "Glycomet 500": ("Glycomet 500mg Tablet", "10 tabs"),
}

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
    cleaned_value = str(value).replace(',', '').strip()
    # Extract the first valid number found (handling potential text around it)
    match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
    if match:
        return float(match.group())
    return 0.0

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
    
    if "emm vee traders" in normalized_supplier:
        # Rate is per Dozen
        return raw_rate / 12.0
    
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
    """
    
    # 1. Calculate Cost Price (CP)
    cp_per_unit = calculate_cost_price(raw_item, supplier_name)
    
    # 2. Parse Quantities and Percents
    qty = parse_float(raw_item.Raw_Quantity)
    discount_percent = parse_float(raw_item.Raw_Discount_Percentage)
    gst_percent = parse_float(raw_item.Raw_GST_Percentage)
    stated_net_amount = parse_float(raw_item.Stated_Net_Amount)
    
    # 3. Calculate Gross Value
    gross_value = qty * cp_per_unit
    
    # 4. Calculate Discount Amount
    discount_amount = round(gross_value * (discount_percent / 100.0), 2)
    
    # 5. Calculate Taxable Value
    taxable_value = round(gross_value - discount_amount, 2)
    
    # 6. Calculate Tax Amount
    tax_amount = round(taxable_value * (gst_percent / 100.0), 2)
    
    # 7. Calculate Total Amount
    calculated_net = round(taxable_value + tax_amount, 2)
    
    # 8. Reconciliation
    diff = abs(calculated_net - stated_net_amount)
    final_net_amount = calculated_net
    
    if diff <= 0.05:
        final_net_amount = stated_net_amount
    
    return {
        "Standard_Quantity": qty,
        "Calculated_Cost_Price_Per_Unit": round(cp_per_unit, 2),
        "Discount_Amount_Currency": discount_amount,
        "Calculated_Taxable_Value": taxable_value,
        "Calculated_Tax_Amount": tax_amount,
        "Net_Line_Amount": final_net_amount,
        "Raw_GST_Percentage": gst_percent,
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
    
    # 3. Merge them
    return {
        **financials,
        "Standard_Item_Name": std_name,
        "Pack_Size_Description": pack_size,
        "Batch_No": raw_item.Batch_No
    }
