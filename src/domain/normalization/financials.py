import re
import math
import logging
from typing import Union, List

logger = logging.getLogger(__name__)

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

    if not cleaned_value:
        return 0.0

    # Extract the first valid number found (handling potential text around it)
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
            pass # Fallback to standard regex if match fails
    
    match = re.search(r'-?\d+(\.\d+)?', cleaned_value)
    if match:
        return float(match.group())
    return 0.0

def parse_quantity(value: Union[str, float, None], free_qty: Union[str, float, None] = 0) -> int:
    """
    Parses a quantity string, handling sums (e.g. '10+2') and rounding UP to nearest integer.
    Rule: 1.86 -> 2, 1.5 -> 2.
    Rule: 1.5 + 1.5 -> 3.0 -> 3.
    """
    if value is None:
        value = 0
    if free_qty is None:
        free_qty = 0
        
    # Helper to clean and parse float
    def clean_float(val):
        if isinstance(val, (float, int)):
            return float(val)
        s = str(val).strip().lower()
        s = re.sub(r'(?:rs\.?|inr|\$|€|£|,)', '', s)
        if not s: return 0.0
        
        # Handle "10+2" inside single string
        if "+" in s:
            try:
                parts = s.split('+')
                return sum(float(re.search(r'-?\d+(\.\d+)?', p).group() or 0) for p in parts if re.search(r'-?\d+(\.\d+)?', p))
            except:
                pass
                
        match = re.search(r'-?\d+(\.\d+)?', s)
        return float(match.group()) if match else 0.0

    billed_q = clean_float(value)
    free_q = clean_float(free_qty)
    
    total_qty = billed_q + free_q
            
    return math.ceil(total_qty)

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> list:
    """
    SMART DIRECTIONAL RECONCILIATION:
    Adjusts line items to match Grand Total based on mathematical directionality.
    """
    if not line_items or grand_total <= 0:
        return line_items
        
    current_sum = sum(float(item.get("Net_Line_Amount", 0)) for item in line_items)
    gap = current_sum - grand_total
    
    if abs(gap) < 0.01:
        # Truly negligible
        return line_items

    logger.info(f"Reconcile: GAP DETECTED. Sum {current_sum:.2f} vs Total {grand_total:.2f} (Gap {gap:.2f})")
    
    # Initialize
    modifier_to_apply = -gap # We always want to negate the gap
    action = "FORCED_MATCH"
    
    # Extract Modifiers for labeling
    g_disc = abs(float(global_modifiers.get("Global_Discount_Amount", 0) or 0))
    g_tax = abs(float(global_modifiers.get("Global_Tax_Amount", 0) or 0) + 
                float(global_modifiers.get("SGST_Amount", 0) or 0) + 
                float(global_modifiers.get("CGST_Amount", 0) or 0) + 
                float(global_modifiers.get("IGST_Amount", 0) or 0))
    
    if gap > 0:
        # Inflation (Sum > Total). Reduce.
        if g_disc > 0:
            action = "APPLY_DISCOUNT_CORRECTION"
            logger.info("Reconcile: Gap attributed to Global Discount.")
        else:
            action = "IMPLICIT_REDUCTION" 
            logger.info("Reconcile: Gap treated as Implicit Reduction/Rounding.")
            
    elif gap < 0:
        # Deflation (Sum < Total). Increase.
        adder_sum = g_tax 
        if adder_sum > 0:
            action = "APPLY_TAX_CORRECTION"
            logger.info("Reconcile: Gap attributed to Global Tax.")
        else:
            action = "IMPLICIT_ADDITION"
            logger.info("Reconcile: Gap treated as Implicit Addition/Rounding.")

    # EXECUTE DISTRIBUTION
    if modifier_to_apply != 0:
        for item in line_items:
            original_net = float(item.get("Net_Line_Amount", 0))
            ratio = original_net / current_sum if current_sum > 0 else 0
            
            share = modifier_to_apply * ratio
            new_net = original_net + share # Add (modifier might be negative)
            
            # Metadata for UI Feedback "Perfect Match"
            correction_factor = new_net / original_net if original_net != 0 else 1.0
            
            item["Net_Line_Amount"] = round(new_net, 2)
            item["Is_Calculated"] = True # New Flag for Frontend UI (Calculator Icon)
            
            # Recalculate Unit Cost
            qty = float(item.get("Standard_Quantity", 1) or 1)
            if qty > 0:
                item["Final_Unit_Cost"] = round(new_net / qty, 2)
            
            # logic_note update
            factor_str = f"{correction_factor:.4f}x"
            # Append specific note
            old_note = item.get("Logic_Note", "")
            item["Logic_Note"] = f"{old_note} [Reconcile: {action}, Factor: {factor_str}]"

    return line_items
