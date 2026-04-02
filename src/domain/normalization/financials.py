import math
import logging
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, List, Dict, Any

logger = logging.getLogger(__name__)

def largest_remainder_allocation(global_total: float, item_weights: List[float]) -> List[float]:
    """
    Hamilton/Largest Remainder Method for precise distribution.
    Distributes a global total across multiple items without rounding loss.
    """
    if not item_weights or global_total == 0:
        return [0.0] * len(item_weights)
    
    total_weight = sum(item_weights)
    if total_weight == 0:
        return [0.0] * len(item_weights)

    # Work in "cents" (integers) using Decimal for fair shares
    total_to_distribute = int(round(global_total * 100))
    weights_dec = [Decimal(str(w)) for w in item_weights]
    total_weight_dec = sum(weights_dec)
    
    # 1. FAIR SHARES (as decimals)
    fair_shares = [(Decimal(str(total_to_distribute)) * w) / total_weight_dec for w in weights_dec]
    
    # 2. QUOTAS (Integer parts)
    quotas = [int(f) for f in fair_shares]
    
    # 3. REMAINDER
    current_sum = sum(quotas)
    remainder = total_to_distribute - current_sum
    
    # 4. RANKING by fractional parts
    fractions = [(f - int(f), i) for i, f in enumerate(fair_shares)]
    # Sort by fractional part descending
    fractions.sort(key=lambda x: x[0], reverse=True)
    
    # 5. DISTRIBUTION of remainder
    for i in range(remainder):
        idx = fractions[i][1]
        quotas[idx] += 1
        
    return [round(q / 100.0, 2) for q in quotas]

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
    # Apply a small rounding epsilon to avoid float artifacts (2.9+0.1=3.0000004 -> ceil=4)
    return math.ceil(round(total_qty, 3))

def calculate_tco_drivers(item_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculates the Total Cost of Ownership (TCO) drivers for a specific item.
    TCO = P_acq + Sum(C_cap + C_serv + C_stor + C_risk) + L_log
    """
    p_acq = float(item_data.get("Final_Unit_Cost") or 0.0)
    if p_acq <= 0:
        return {
            "capital_cost": 0.0, "service_cost": 0.0, "storage_cost": 0.0,
            "risk_cost": 0.0, "logistics_cost": 0.0, "tco": 0.0
        }

    # 1. Logistics Cost (L_log) - Baseline 2%
    l_log = round(p_acq * 0.02, 2)

    # 2. Capital Cost (C_cap) - Opportunity cost 1%
    c_cap = round(p_acq * 0.01, 2)

    # 3. Service Cost (C_serv) - Administrative 0.5%
    c_serv = round(p_acq * 0.005, 2)

    # 4. Storage Cost (C_stor)
    # Premium for Cold Chain / Biologics
    product_name = str(item_data.get("Product") or item_data.get("Standard_Item_Name") or "").lower()
    category = str(item_data.get("Category") or "").lower()
    
    cold_chain_keywords = ["huminsulin", "insulin", "biologic", "cold chain", "refrigerated", "injection", "vaccine"]
    is_cold_chain = any(kw in product_name or kw in category for kw in cold_chain_keywords)
    
    if is_cold_chain:
        c_stor = round(p_acq * 0.15, 2) # 15% Storage Premium
    else:
        c_stor = round(p_acq * 0.02, 2) # 2% Standard Storage

    # 5. Risk Cost (C_risk)
    # Heavy increase if expiry is < 6 months away
    c_risk = round(p_acq * 0.01, 2) # Baseline 1%
    expiry_str = item_data.get("Expiry") or item_data.get("Expiry_Date")
    
    if expiry_str:
        try:
            # Common formats: MM/YY, DD/MM/YYYY, etc.
            # We'll try a few broad parsers
            expiry_date = None
            if "/" in expiry_str:
                parts = expiry_str.split("/")
                if len(parts) == 2: # MM/YY
                    m, y = int(parts[0]), int(parts[1])
                    if y < 100: y += 2000
                    expiry_date = date(y, m, 1)
                elif len(parts) == 3: # DD/MM/YYYY
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100: y += 2000
                    expiry_date = date(y, m, d)
            
            if expiry_date:
                today = date.today()
                days_to_expiry = (expiry_date - today).days
                if days_to_expiry < 180: # < 6 months
                    c_risk = round(p_acq * 0.25, 2) # 25% Risk Premium
                    logger.info(f"TCO: Applied Risk Premium for near-expiry item: {product_name} ({days_to_expiry} days left)")
        except Exception as e:
            logger.warning(f"TCO: Could not parse expiry date '{expiry_str}': {e}")

    # Final TCO Sum
    tco = round(p_acq + c_cap + c_serv + c_stor + c_risk + l_log, 2)
    
    return {
        "capital_cost": c_cap,
        "service_cost": c_serv,
        "storage_cost": c_stor,
        "risk_cost": c_risk,
        "logistics_cost": l_log,
        "tco": tco
    }

def is_return_item(item: Dict[str, Any]) -> bool:
    """
    Identifies if a line item is a Sales Return, Credit Note, or Adjustment.
    """
    desc = str(item.get("Product") or item.get("Standard_Item_Name") or "").upper()
    amount = parse_float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0)
    
    # Check for negative amount
    if amount < 0:
        return True
        
    # Check for keywords
    return_keywords = ["RETURN:", "SALES RET", "SALE RET", "CR NOTE", "CREDIT NOTE", "ADJUSTMENT", "LESS:", "SCHEME AMT", "SCH AMT"]
    return any(kw in desc for kw in return_keywords)

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> dict:
    """
    PERFECT LEDGER MATH ENGINE:
    Implements a Strict Ledger Equation and Proportional Allocation.
    Detects if the invoice is 'PER_ITEM' (modifiers included in lines) or 'GLOBAL' (modifiers at footer).
    """
    if not line_items:
        return {"line_items": line_items, "calculated_stats": {}}

    grand_total = float(grand_total or 0.0)

    # 1. Calculate Base Sums from Line Items
    # net_sum: Sum of final row totals (Post-tax, post-line-discount)
    # gross_sum: Sum of raw row totals (Pre-tax, pre-global-discount)
    
    # CRITICAL FIX: Separate Positive items from Returns
    positive_items = [item for item in line_items if not is_return_item(item)]
    return_items = [item for item in line_items if is_return_item(item)]
    
    positive_sum = sum(float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0) for item in positive_items)
    return_sum = sum(abs(float(return_item.get("Net_Line_Amount") or return_item.get("Amount") or 0.0)) for return_item in return_items)
    
    # Net Line Sum = Positive - Returns
    net_sum = positive_sum - return_sum
    # Default Gross Sum to Net Sum for now
    gross_sum = net_sum
    
    stated_sub_total = parse_float(
        global_modifiers.get("sub_total") or 
        global_modifiers.get("Sub_Total") or 0.0
    )
    
    # REPAIR LOGIC: Compare stated_sub_total against the sum of POSITIVE items (non-returns).
    # If the subtotal matches the positive items, it means the return was subtracted AFTER subtotal.
    # If the subtotal matches net_sum, it means the return was subtracted BEFORE subtotal.
    if stated_sub_total > 0:
        if abs(stated_sub_total - net_sum) < 1.0:
            gross_sum = net_sum
            logger.info("Financials: Sub Total matches Net Sum (Return already subtracted).")
        elif abs(stated_sub_total - positive_sum) < 1.0:
            gross_sum = positive_sum
            logger.info("Financials: Sub Total matches Positive Sum (Return subtracted after subtotal).")
        else:
            gross_sum = stated_sub_total
            logger.info(f"Financials: Using Stated Sub Total {stated_sub_total}")

    # 2. Extract Modifier values
    global_discount = abs(parse_float(
        global_modifiers.get("global_discount") or 
        global_modifiers.get("Global_Discount_Amount") or 
        global_modifiers.get("discount") or 0.0
    ))
    total_sgst = abs(parse_float(
        global_modifiers.get("total_sgst") or 
        global_modifiers.get("SGST_Amount") or 
        global_modifiers.get("sgst") or 0.0
    ))
    total_cgst = abs(parse_float(
        global_modifiers.get("total_cgst") or 
        global_modifiers.get("CGST_Amount") or 
        global_modifiers.get("cgst") or 0.0
    ))
    credit_note = abs(parse_float(
        global_modifiers.get("credit_note_amount") or 
        global_modifiers.get("Credit_Note_Amount") or 
        global_modifiers.get("credit_note") or 
        global_modifiers.get("CN_Amount") or 
        global_modifiers.get("less_cn") or 0.0
    ))
    # If we identified return line items, and they match the credit note amount, avoid double counting
    if return_sum > 0 and abs(return_sum - credit_note) < 1.0:
        logger.info(f"Financials: Return items ({return_sum}) already captured. Deduplicating Credit Note.")
        credit_note = 0.0
    elif return_sum > 0:
        # If both exist and differ, the line items take priority but we keep the difference if large?
        # Standard: Line items are more accurate than footer extraction.
        # But for now, we'll sum them if they are distinct.
        pass

    extra_charges = abs(parse_float(
        global_modifiers.get("extra_charges") or 
        global_modifiers.get("Extra_Charges") or 0.0
    ))
    round_off = parse_float(
        global_modifiers.get("round_off") or 
        global_modifiers.get("Round_Off") or 0.0
    )
    
    # 3. Mode Detection (Disambiguation)
    # Equation A: net_sum + RoundOff - CN + Extras == GrandTotal -> PER_ITEM (Items are final)
    # Equation B: gross_sum - Discount + Tax + RoundOff - CN + Extras == GrandTotal -> GLOBAL (Footer calculates total)
    
    eq_a_result = net_sum + round_off - credit_note + extra_charges
    eq_b_result = gross_sum - global_discount + total_sgst + total_cgst + round_off - credit_note + extra_charges
    
    # 3. Mode Detection (Smallest Gap Wins)
    gap_a = abs(eq_a_result - grand_total)
    gap_b = abs(eq_b_result - grand_total)
    
    # BIAS RULE: If taxes are present in the headers, favor GLOBAL mode.
    if total_sgst > 0 or total_cgst > 0:
        gap_a += 2.0 
        logger.info(f"Financials: Bias applied (Taxes found). Gap A(PER_ITEM):{gap_a-2.0:.2f}, Gap B(GLOBAL):{gap_b:.2f}")

    if gap_b <= gap_a: # Favor GLOBAL on tie or better match
        mode = "GLOBAL"
        line_sum = gross_sum
        logger.info(f"Financials: Detected GLOBAL mode")
    else:
        mode = "PER_ITEM"
        # In PER_ITEM mode, line items are tax-inclusive/discounted.
        line_sgst = sum(parse_float(item.get("SGST_Amount") or item.get("total_sgst") or 0.0) for item in line_items)
        line_cgst = sum(parse_float(item.get("CGST_Amount") or item.get("total_cgst") or 0.0) for item in line_items)
        line_disc = sum(parse_float(item.get("Discount_Amount") or item.get("SCH_Amt") or 0.0) for item in line_items)
        
        if line_sgst > 0 or line_cgst > 0 or line_disc > 0:
            total_sgst = line_sgst
            total_cgst = line_cgst
            global_discount = line_disc
            line_sum = net_sum - total_sgst - total_cgst + global_discount
        else:
            line_sum = net_sum
            global_discount = 0.0
            total_sgst = 0.0
            total_cgst = 0.0
            
        logger.info(f"Financials: Detected PER_ITEM mode")

    # 4. Rounding Discovery
    calculated_pre_round = eq_a_result - round_off if mode == "PER_ITEM" else eq_b_result - round_off
    discovered_gap = grand_total - calculated_pre_round
    
    if abs(discovered_gap) < 0.99:
        round_off = round(discovered_gap, 2)
    elif grand_total == 0:
        nearest_int = round(calculated_pre_round)
        auto_gap = nearest_int - calculated_pre_round
        if abs(auto_gap) < 0.50:
            round_off = round(auto_gap, 2)

    # 4b. Tax Inference
    if (total_sgst < 0.01 and total_cgst < 0.01):
        inferred_tax = 0.0
        for item in line_items:
            net_amt = float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0)
            gst_pct = float(item.get("Raw_GST_Percentage") or (float(item.get("SGST_Percent") or 0.0) + float(item.get("CGST_Percent") or 0.0)))
            if gst_pct > 0:
                inferred_tax += net_amt - (net_amt / (1 + (gst_pct / 100)))
        
        if inferred_tax > 0.1:
             total_sgst = round(inferred_tax / 2, 2)
             total_cgst = round(inferred_tax / 2, 2)

    # 4e. Final Ledger Result
    if mode == "PER_ITEM":
        raw_calculated_grand_total = line_sum + round_off - credit_note + extra_charges
    else:
        raw_calculated_grand_total = gross_sum - global_discount + total_sgst + total_cgst + round_off - credit_note + extra_charges
        
    taxable_value = line_sum if mode == "PER_ITEM" else (line_sum - global_discount)

    # 5. Consistency Check
    gap = abs(raw_calculated_grand_total - grand_total)
    if gap > 2.0 and grand_total > 0:
        error_msg = f"Financial Mismatch: {raw_calculated_grand_total:.2f} vs {grand_total:.2f}"
        if line_items: line_items[0]["Validation_Error"] = error_msg

    exact_gap = grand_total - raw_calculated_grand_total
    if abs(exact_gap) > 0.01 and grand_total > 0:
        extra_charges += exact_gap
        calculated_grand_total = grand_total
    else:
        calculated_grand_total = raw_calculated_grand_total

    # 6. Perfect Proportional Allocation for Effective Landing Cost
    # CRITICAL: Exclude Returns from Weights
    item_weights = []
    for item in line_items:
        if is_return_item(item):
            item_weights.append(0.0)
        else:
            item_weights.append(float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0))
            
    # Distribution
    landed_costs = largest_remainder_allocation(grand_total, item_weights)
    
    for i, item in enumerate(line_items):
        if is_return_item(item):
            item["effective_landing_cost"] = 0.0
            item["Final_Unit_Cost"] = 0.0
            item["Logic_Note"] = f"{item.get('Logic_Note', '')} [RETURN: Excluded from Landed Cost]".strip()
        else:
            item["effective_landing_cost"] = landed_costs[i]
            qty = float(item.get("Standard_Quantity") or item.get("Qty", 1) or 1)
            item["Final_Unit_Cost"] = round(item["effective_landing_cost"] / qty, 2) if qty > 0 else 0.0
            item["Logic_Note"] = f"{item.get('Logic_Note', '')} [Landed: ₹{item['effective_landing_cost']:.2f}]".strip()

        # 7. Enterprise TCO Calculation
        tco_data = calculate_tco_drivers(item)
        item.update(tco_data)
        item["Logic_Note"] += f" [TCO: ₹{item['tco']:.2f}]"

    return {
        "line_items": line_items,
        "mode": mode,
        "calculated_stats": {
            "sub_total": round(line_sum, 2),
            "global_discount": round(global_discount, 2),
            "taxable_value": round(taxable_value, 2),
            "total_sgst": round(total_sgst, 2),
            "total_cgst": round(total_cgst, 2),
            "credit_note_amount": round(credit_note, 2),
            "extra_charges": round(extra_charges, 2),
            "round_off": round(round_off, 2),
            "grand_total": round(calculated_grand_total, 2)
        }
    }
