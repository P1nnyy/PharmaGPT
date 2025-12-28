import re
import math
from typing import Union

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
    cleaned_value = str(value).strip().lower()
    cleaned_value = re.sub(r'(?:rs\.?|inr|\$|€|£)', '', cleaned_value).strip()
    # Remove commas
    cleaned_value = cleaned_value.replace(',', '')

    if not cleaned_value:
        return 0.0
        
    # Handle "Billed + Free" formats (e.g. "10+2", "4.50+.50")
    if "+" in cleaned_value:
        try:
            parts = cleaned_value.split('+')
            # Extract the FIRST number found (Billed Qty)
            first_part = parts[0]
            match = re.search(r'\d+(\.\d+)?', first_part)
            if match:
                return float(match.group())
        except:
            pass 
    
    match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
    if match:
        return float(match.group())
    return 0.0

def parse_quantity(value: Union[str, float, None]) -> int:
    """
    Parses a quantity string, handling sums (e.g. '10+2') and rounding UP to nearest integer.
    """
    if value is None:
        return 0
        
    if isinstance(value, (float, int)):
        return math.ceil(value)
        
    cleaned_value = str(value).strip().lower()
    cleaned_value = re.sub(r'(?:rs\.?|inr|\$|€|£)', '', cleaned_value).strip()
    cleaned_value = cleaned_value.replace(',', '')
    
    if not cleaned_value:
        return 0
        
    total_qty = 0.0
    
    # Check for split sums "1.5 + 1.5" or "10+2"
    if "+" in cleaned_value:
        parts = cleaned_value.split('+')
        for part in parts:
            match = re.search(r'-?\d+(\.\d+)?', part.strip())
            if match:
                total_qty += float(match.group())
    else:
        match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
        if match:
            total_qty = float(match.group())
            
    return float(total_qty)
