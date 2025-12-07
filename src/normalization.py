import re
from typing import Union
from src.schemas import RawLineItem

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
    
    Rules:
    - Emm Vee Traders: Rate is per dozen (Rate/Doz), so CP = Rate / 12.
    - Zero Quantity: If quantity is effectively 0, treat as 0 value (return 0.0).
    - Default: CP = Rate (Rate per unit/pack).
    """
    
    # 1. Parse inputs
    raw_qty = parse_float(raw_item.Raw_Quantity)
    
    # Check for primary rate column first, fallback to secondary if needed (though logic usually relies on primary)
    # The prompt implies Raw_Rate_Column_1 is the main one for Rate/Doz logic.
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

def calculate_financials(raw_item: RawLineItem, supplier_name: str) -> dict:
    """
    Calculates financial figures including Cost Price, Discount Amount, Taxable Value, and Net Amount.
    Performs reconciliation with stated net amount.
    
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
    # Gross Value = Quantity * CP
    gross_value = qty * cp_per_unit
    
    # 4. Calculate Discount Amount
    discount_amount = gross_value * (discount_percent / 100.0)
    
    # 5. Calculate Taxable Value
    taxable_value = gross_value - discount_amount
    
    # 6. Calculate Tax Amount
    tax_amount = taxable_value * (gst_percent / 100.0)
    
    # 7. Calculate Total Amount
    calculated_net = taxable_value + tax_amount
    
    # 8. Reconciliation
    # Tolerance: +/- 0.05
    diff = abs(calculated_net - stated_net_amount)
    final_net_amount = calculated_net
    
    if diff <= 0.05:
        # If within tolerance, use stated amount (Round Off logic)
        final_net_amount = stated_net_amount
        # In a real system, we might log this: print(f"Round off applied. Diff: {diff}")
    else:
        # Outside tolerance: Use calculated amount (or flag error). 
        # Prompt says "If they differ due to minor rounding... use Stated_Net_Amount".
        # Implicitly, if they differ significantly, we strictly mostly trust calculation or flag it.
        # Here we stick to calculated amount as the "truth" derived from components, 
        # unless specifically asked to overwrite with stated for large diffs (unlikely).
        pass

    return {
        "Standard_Quantity": qty,
        "Calculated_Cost_Price_Per_Unit": cp_per_unit,
        "Discount_Amount_Currency": discount_amount,
        "Calculated_Taxable_Value": taxable_value,
        "Net_Line_Amount": final_net_amount,
        # Missing fields from NormalizedLineItem that aren't calculated here but required:
        # Standard_Item_Name, Pack_Size_Description - will need to be filled from elsewhere or dummy.
    }
