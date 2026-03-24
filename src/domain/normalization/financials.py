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
            # UDPATED REGEX: Handle .250 as 0.250
            match = re.search(r'-?(\d+\.\d+|\d+|\.\d+)', first_part)
            if match:
                return float(match.group())
        except:
            pass # Fallback to standard regex if match fails
    
    # UDPATED REGEX: Handle .250 as 0.250
    match = re.search(r'-?(\d+\.\d+|\d+|\.\d+)', cleaned_value)
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
                # UDPATED REGEX: Handle .250 as 0.250
                return sum(float(re.search(r'-?(\d+\.\d+|\d+|\.\d+)', p).group() or 0) for p in parts if re.search(r'-?(\d+\.\d+|\d+|\.\d+)', p))
            except:
                pass
                
        # UDPATED REGEX: Handle .250 as 0.250
        match = re.search(r'-?(\d+\.\d+|\d+|\.\d+)', s)
        return float(match.group()) if match else 0.0

    billed_q = clean_float(value)
    free_q = clean_float(free_qty)
    
    total_qty = billed_q + free_q
            
    return math.ceil(total_qty)

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> list:
    """
    PERFECT LEDGER MATH ENGINE:
    Implements a Strict Ledger Equation and Proportional Allocation.
    """
    if not line_items:
        return line_items

    # 1. Calculate Sub-Total from Line Items
    # Robust: Check for Net_Line_Amount (Normalized) or Amount (Raw)
    calculated_sub_total = sum(float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0) for item in line_items)
    
    # 2. Extract Modifier values (Robust casing for schema compatibility)
    # Strategy: Use absolute values to ensure subtraction logic works regardless of OCR sign (-)
    global_discount = abs(parse_float(global_modifiers.get("global_discount") or global_modifiers.get("Global_Discount_Amount") or 0.0))
    total_sgst = abs(parse_float(global_modifiers.get("total_sgst") or global_modifiers.get("SGST_Amount") or 0.0))
    total_cgst = abs(parse_float(global_modifiers.get("total_cgst") or global_modifiers.get("CGST_Amount") or 0.0))
    round_off = parse_float(global_modifiers.get("round_off") or global_modifiers.get("Round_Off") or 0.0) # RO can be negative/positive for adjustment
    
    # 3. Calculate Derived Values
    taxable_value = calculated_sub_total - global_discount
    expected_grand_total = taxable_value + total_sgst + total_cgst + round_off
    
    # 4. Consistency Check (Margin 1.0)
    gap = abs(expected_grand_total - grand_total)
    if gap > 1.0:
        error_msg = f"Financial Mismatch: Expected Grand Total {expected_grand_total:.2f} (Sub:{calculated_sub_total:.2f} - Disc:{global_discount:.2f} + GST:{total_sgst+total_cgst:.2f} + RO:{round_off:.2f}) does not match Stated Grand Total {grand_total:.2f} (Gap: {gap:.2f})"
        logger.error(error_msg)
        # We append this to the first item's logic note or a general state error if available
        if line_items:
            line_items[0]["Validation_Error"] = error_msg

    # 5. Proportional Allocation for Effective Landing Cost
    total_calculated_tax = 0.0
    for item in line_items:
        # UPDATED: Use Amount or Net_Line_Amount
        item_amount = float(item.get("Net_Line_Amount") or item.get("Amount") or item.get("Stated_Net_Amount") or 0.0)
        
        # Safe Weight Ratio
        weight_ratio = item_amount / calculated_sub_total if calculated_sub_total > 0 else 0
        
        # Allocation
        item_discount_share = global_discount * weight_ratio
        item_taxable = item_amount - item_discount_share
        
        # Tax Calculation (Default 5% if missing)
        gst_percent = (float(item.get("SGST_Percent") or 0.0) + 
                       float(item.get("CGST_Percent") or 0.0) + 
                       float(item.get("IGST_Percent") or 0.0) +
                       float(item.get("Raw_GST_Percentage") or 0.0))
                       
        if gst_percent <= 0:
            gst_percent = 5.0 # User's default
            
        item_tax = item_taxable * (gst_percent / 100)
        total_calculated_tax += item_tax
        
        # Final Landed Cost
        item["effective_landing_cost"] = round(item_taxable + item_tax, 2)
        
        # Calculate Unit Cost (Landed)
        qty = float(item.get("Qty", 1) or 1)
        if qty > 0:
            item["Final_Unit_Cost"] = round(item["effective_landing_cost"] / qty, 2)
            
        # Logic Note Update
        old_note = item.get("Logic_Note", "")
        item["Logic_Note"] = f"{old_note} [Ledger: Taxable {item_taxable:.2f}, Tax {item_tax:.2f}, Landing {item['effective_landing_cost']:.2f}]"

    # Return items AND calculated footer stats for fallback healing
    return {
        "line_items": line_items,
        "calculated_stats": {
            "sub_total": round(calculated_sub_total, 2),
            "taxable_value": round(taxable_value, 2),
            "total_gst": round(total_calculated_tax, 2),
            "grand_total": round(calculated_sub_total - global_discount + total_calculated_tax + round_off, 2)
        }
    }
