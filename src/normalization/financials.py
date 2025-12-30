import logging
# math is imported inside but good to have
import math

def reconcile_financials(line_items: list, global_modifiers: dict, grand_total: float) -> list:
    """
    SMART DIRECTIONAL RECONCILIATION:
    Adjusts line items to match Grand Total based on mathematical directionality.
    """
    if not line_items or grand_total <= 0:
        return line_items
        
    current_sum = sum(float(item.get("Net_Line_Amount", 0)) for item in line_items)
    gap = current_sum - grand_total
    
    # Threshold for "Close Enough"
    # UPDATED: Tightened to 0.1% (or 0.5 Rs) because Pharma margins are thin.
    if abs(gap) < max(0.5, grand_total * 0.001):
        logger = logging.getLogger("normalization")
        logger.info(f"Reconcile: Sum {current_sum:.2f} matches Total {grand_total:.2f}. No changes.")
        return line_items

    logger = logging.getLogger("normalization")
    logger.info(f"Reconcile: GAP DETECTED. Sum {current_sum:.2f} vs Total {grand_total:.2f} (Gap {gap:.2f})")
    logger.info(f"Reconcile: Input Modifiers: {global_modifiers}")

    # Extract Modifiers
    g_disc = abs(float(global_modifiers.get("Global_Discount_Amount", 0) or 0))
    g_tax = abs(float(global_modifiers.get("Global_Tax_Amount", 0) or 0) + 
                float(global_modifiers.get("SGST_Amount", 0) or 0) + 
                float(global_modifiers.get("CGST_Amount", 0) or 0) + 
                float(global_modifiers.get("IGST_Amount", 0) or 0))
    freight = abs(float(global_modifiers.get("Freight_Charges", 0) or 0))
    
    modifier_to_apply = 0.0
    action = "NONE"
    
    if gap > 0:
        # Inflation. Reduce.
        logger.info(f"Reconcile: Inflation Detected (Gap +{gap:.2f}). Looking for Reducers...")
        if g_disc > 0:
            modifier_to_apply = -gap 
            action = "APPLY_DISCOUNT_CORRECTION"
            logger.info(f"Reconcile: Found Global Discount ({g_disc}). Applying Correction of -{gap:.2f} to match Total.")
        else:
            # Check for Implicit Discount (Small Gap < 5%)
            gap_percentage = gap / grand_total if grand_total > 0 else 0
            if gap_percentage < 0.05:
                modifier_to_apply = -gap
                action = "APPLY_IMPLICIT_DISCOUNT"
                logger.info(f"Reconcile: Implicit Discount Detected ({gap_percentage:.1%}). No explicit discount found, but gap is small. Force Reconciling.")
            else:
                logger.warning(f"Reconcile: No Discount found and gap ({gap_percentage:.1%}) is too large for implicit correction. Doing nothing (Safe Mode).")
            
    elif gap < 0:
        # Deflation. Increase.
        logger.info(f"Reconcile: Deflation Detected (Gap {gap:.2f}). Looking for Adders...")
        adder_sum = g_tax + freight
        if adder_sum > 0:
            modifier_to_apply = -gap # -(-gap) = +gap
            action = "APPLY_TAX_FREIGHT_CORRECTION"
            logger.info(f"Reconcile: Found Tax/Freight ({adder_sum}). Applying Correction of +{abs(gap):.2f} to match Total.")
        else:
             logger.warning("Reconcile: No Tax/Freight found to increase value. Doing nothing (Safe Mode).")

    if modifier_to_apply != 0:
        for item in line_items:
            original_net = float(item.get("Net_Line_Amount", 0))
            ratio = original_net / current_sum if current_sum > 0 else 0
            
            share = modifier_to_apply * ratio
            new_net = original_net + share 
            
            item["Net_Line_Amount"] = round(new_net, 2)
            
            qty = float(item.get("Standard_Quantity", 1) or 1)
            if qty > 0:
                item["Final_Unit_Cost"] = round(new_net / qty, 2)
            
            item["Logic_Note"] = item.get("Logic_Note", "") + f" [Reconcile: {action}]"

    return line_items
