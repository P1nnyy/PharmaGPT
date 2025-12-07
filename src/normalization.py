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
