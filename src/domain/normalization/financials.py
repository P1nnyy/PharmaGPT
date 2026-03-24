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

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> dict:
    """
    PERFECT LEDGER MATH ENGINE:
    Implements a Strict Ledger Equation and Proportional Allocation.
    Detects if the invoice is 'PER_ITEM' (modifiers included in lines) or 'GLOBAL' (modifiers at footer).
    """
    if not line_items:
        return {"line_items": line_items, "calculated_stats": {}}

    # 1. Calculate Base Sum from Line Items
    # Robust: Check for Net_Line_Amount (Normalized) or Amount (Raw)
    line_sum = sum(float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0) for item in line_items)
    
    # 2. Extract Modifier values (Robust casing for schema compatibility)
    # Strategy: Use absolute values to ensure subtraction logic works regardless of OCR sign (-)
    global_discount = abs(parse_float(global_modifiers.get("global_discount") or global_modifiers.get("Global_Discount_Amount") or 0.0))
    total_sgst = abs(parse_float(global_modifiers.get("total_sgst") or global_modifiers.get("SGST_Amount") or 0.0))
    total_cgst = abs(parse_float(global_modifiers.get("total_cgst") or global_modifiers.get("CGST_Amount") or 0.0))
    round_off = parse_float(global_modifiers.get("round_off") or global_modifiers.get("Round_Off") or 0.0)
    
    # 3. Mode Detection (Disambiguation)
    # Equation A: LineSum + RoundOff == GrandTotal -> PER_ITEM
    # Equation B: LineSum - Discount + Tax + RoundOff == GrandTotal -> GLOBAL
    
    eq_a_result = line_sum + round_off
    eq_b_result = line_sum - global_discount + total_sgst + total_cgst + round_off
    
    mode = "GLOBAL" # Default
    if abs(eq_a_result - grand_total) < 2.0:
        mode = "PER_ITEM"
        logger.info(f"Financials: Detected PER_ITEM mode (Sum {line_sum:.2f} matches Grand Total {grand_total:.2f})")
    elif abs(eq_b_result - grand_total) < 2.0:
        mode = "GLOBAL"
        logger.info(f"Financials: Detected GLOBAL mode (Sum {line_sum:.2f} - Disc {global_discount:.2f} + Tax {total_sgst+total_cgst:.2f} matches Grand Total {grand_total:.2f})")
    else:
        # If neither matches perfectly, use whichever is closer as the working assumption
        gap_a = abs(eq_a_result - grand_total)
        gap_b = abs(eq_b_result - grand_total)
        mode = "PER_ITEM" if gap_a < gap_b else "GLOBAL"
        logger.warning(f"Financials: Ambiguous Mode (Gap A: {gap_a:.2f}, Gap B: {gap_b:.2f}). Operating in fallback mode: {mode}")

    # 4. Automated Rounding Discovery (The "Paise" Fix)
    # If the gap is small (< 1.0), absorb it into round_off to ensure a perfect match
    calculated_pre_round = eq_a_result - round_off if mode == "PER_ITEM" else eq_b_result - round_off
    discovered_gap = grand_total - calculated_pre_round
    if abs(discovered_gap) < 2.0:
        round_off = round(discovered_gap, 2)
        logger.info(f"Financials: Discovered Round-Off: {round_off:.2f}")

    # 4b. Tax Inference (CM Associates Recovery)
    # If SGST/CGST in footer are 0 but Grand Total still doesn't match, infer them from line items
    current_gap = abs((line_sum - global_discount + total_sgst + total_cgst + round_off) - grand_total)
    if mode == "GLOBAL" and current_gap > 5.0 and (total_sgst == 0 or total_cgst == 0):
        inferred_tax = 0.0
        for item in line_items:
            item_amount = float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0)
            weight_ratio = item_amount / line_sum if line_sum > 0 else 0
            item_disc = global_discount * weight_ratio
            item_taxable = item_amount - item_disc
            raw_gst_pct = float(item.get("Raw_GST_Percentage") or 0.0)
            sum_gst_pct = (float(item.get("SGST_Percent") or 0.0) + float(item.get("CGST_Percent") or 0.0))
            gst_pct = raw_gst_pct if raw_gst_pct > 0 else sum_gst_pct
            if gst_pct <= 0: gst_pct = 5.0 # Fallback for inference
            inferred_tax += item_taxable * (gst_pct / 100)
        
        # If inferred tax explains the gap better, use it
        new_gap = abs((line_sum - global_discount + inferred_tax + round_off) - grand_total)
        if new_gap < current_gap:
             total_sgst = round(inferred_tax / 2, 2)
             total_cgst = round(inferred_tax / 2, 2)
             logger.info(f"Financials: Inferred Tax {inferred_tax:.2f} (SGST: {total_sgst}) to close gap from {current_gap:.2f} to {new_gap:.2f}")

    # 4c. Final Ledger Result
    calculated_grand_total = (line_sum + round_off) if mode == "PER_ITEM" else (line_sum - global_discount + total_sgst + total_cgst + round_off)
    taxable_value = line_sum if mode == "PER_ITEM" else (line_sum - global_discount)

    # 5. Consistency Check (Audit Flag)
    gap = abs(calculated_grand_total - grand_total)
    if gap > 2.0:
        error_msg = f"Financial Mismatch: Expected {calculated_grand_total:.2f} (Mode:{mode}) does not match Stated {grand_total:.2f} (Gap: {gap:.2f})"
        logger.error(error_msg)
        if line_items:
            line_items[0]["Validation_Error"] = error_msg

    # 6. Proportional Allocation for Effective Landing Cost
    for item in line_items:
        # Use Net_Line_Amount or fallback
        item_amount = float(item.get("Net_Line_Amount") or item.get("Amount") or item.get("Stated_Net_Amount") or 0.0)
        weight_ratio = item_amount / line_sum if line_sum > 0 else 0
        
        if mode == "PER_ITEM":
            # Items ALREADY have tax and discount included
            item["effective_landing_cost"] = round(item_amount, 2)
        else:
            # GLOBAL Mode: Allocate discount and calculate tax
            item_discount_share = global_discount * weight_ratio
            item_taxable = item_amount - item_discount_share
            
            # --- GST PRIORITY FIX (Against Double Taxation) ---
            # Priority 1: Raw_GST_Percentage (Master value from OCR/Standardization)
            # Priority 2: SGST + CGST + IGST
            raw_gst_pct = float(item.get("Raw_GST_Percentage") or 0.0)
            sum_gst_pct = (float(item.get("SGST_Percent") or 0.0) + 
                           float(item.get("CGST_Percent") or 0.0) + 
                           float(item.get("IGST_Percent") or 0.0))
            
            # If Raw_GST exists, use it. Only use sum if Raw_GST is 0.
            gst_percent = raw_gst_pct if raw_gst_pct > 0 else sum_gst_pct
            
            # Global Fallback (only if absolutely no tax evidence but footer says tax exists)
            if gst_percent <= 0 and (total_sgst > 0 or total_cgst > 0): 
                gst_percent = 5.0 
            
            item_tax = item_taxable * (gst_percent / 100)
            item["effective_landing_cost"] = round(item_taxable + item_tax, 2)
            item["Calculated_GST_Rate"] = gst_percent
        
        # Calculate Unit Cost (Landed)
        qty = float(item.get("Qty", 1) or 1)
        if qty > 0:
            item["Final_Unit_Cost"] = round(item["effective_landing_cost"] / qty, 2)
            
        # Logic Note Update
        old_note = item.get("Logic_Note", "")
        item["Logic_Note"] = f"{old_note} [Landed: {item['effective_landing_cost']:.2f}]".strip()

    return {
        "line_items": line_items,
        "mode": mode,
        "round_off": round_off, # Pass back the discovered value
        "calculated_stats": {
            "sub_total": round(line_sum, 2),
            "taxable_value": round(taxable_value, 2),
            "round_off": round(round_off, 2),
            "grand_total": round(calculated_grand_total, 2)
        }
    }
