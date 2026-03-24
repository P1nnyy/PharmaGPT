from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("solver")

async def apply_correction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Solver Node.
    1. Applies the Critic's correction factor to calculate strict Landed Cost.
    2. Auto-calculates Sales Rates (Rate A/B/C) based on MRP (if available) or Cost + Margin.
    """
    # PREFER: 'line_items' (Clean)
    # FALLBACK: 'line_item_fragments' (Dirty)
    lines = state.get("line_items") or state.get("line_item_fragments", [])
    
    correction_factor = state.get("correction_factor", 1.0)
    
    # USER PREFERENCE: FORCED MATCH ALWAYS
    # Removed 0.9 < factor < 1.1 threshold. We always apply it now.
    pass
        
    logger.info(f"Solver: Applying Final Correction Factor {correction_factor} to {len(lines)} items.")
    
    updated_lines = []
    for item in lines:
        try:
            # UPDATED: Use Amount
            raw_net = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            qty = float(item.get("Qty") or 1)
            
            # 1. Sanctify Product Name
            if not item.get("Product") or str(item.get("Product")).lower() == "none":
                 item["Product"] = "Unknown Item"
                 item["Logic_Note"] = item.get("Logic_Note", "") + " [Missing Name Fixed]"

            # 2. Adjust Total Cost to match the Check (Landed Cost)
            new_net = round(raw_net * correction_factor, 2)
            
            # 3. Recalculate Unit Rate (The SHOP'S BUYING PRICE)
            # This is the most critical number for the shop user!
            cost_price = round(new_net / qty, 2) if qty > 0 else 0
            
            item["Net_Line_Amount"] = new_net
            item["Final_Unit_Cost"] = cost_price # Standardized key for Database
            item["Calculated_Cost_Price_Per_Unit"] = cost_price # Legacy key
            
            item["Logic_Note"] = (item.get("Logic_Note", "") + f" [Auto-Adjusted {correction_factor:.4f}]").strip()
            
            # --- 4. SALES RATE LOGIC (Point D) ---
            mrp = float(item.get("MRP") or 0)
            
            if mrp > 0:
                # SCENARIO A: MRP EXISTS
                # Rate A = MRP (Retail)
                # Rate B = MRP - 10% (Loyalty)
                # Rate C = MRP - 20% (Wholesale)
                item["Sales_Rate_A"] = mrp
                item["Sales_Rate_B"] = round(mrp * 0.90, 2)
                item["Sales_Rate_C"] = round(mrp * 0.80, 2)
                item["Logic_Note"] += " [Rates: Derived from MRP]"
            else:
                # SCENARIO B: NO MRP (Use Margins on Landed Cost)
                # Rate A = Cost + 50%
                # Rate B = Cost + 30%
                # Rate C = Cost + 20%
                item["Sales_Rate_A"] = round(cost_price * 1.50, 2)
                item["Sales_Rate_B"] = round(cost_price * 1.30, 2)
                item["Sales_Rate_C"] = round(cost_price * 1.20, 2)
                item["Logic_Note"] += " [Rates: Cost + Margin]"

            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Error: {e}")
            updated_lines.append(item)
        
    # Reconstruct Final Output
    headers = state.get("global_modifiers", {})
    final_json = headers.copy()
    final_json["Line_Items"] = updated_lines
    
    # --- FOOTER HEALING (The "Grand Total Fix") ---
    # Perform math reconciliation to get calculated fallbacks
    from src.domain.normalization.financials import reconcile_financials, parse_float
    
    # For reconciliation, we need a "Stated Grand Total" anchor. 
    # Use extracted one or fallback to 0.
    stated_total = parse_float(headers.get("Stated_Grand_Total") or headers.get("grand_total") or 0.0)
    
    recon_results = reconcile_financials(updated_lines, headers, stated_total)
    calc_stats = recon_results.get("calculated_stats", {})
    
    # HEAL: If extracted totals are missing/zero, use calculated ones
    # This fixes the "₹0.00" issue in the Frontend when Footer extraction fails.
    if not parse_float(final_json.get("sub_total")):
        logger.info(f"Solver Healing: sub_total filled from math -> {calc_stats['sub_total']}")
        final_json["sub_total"] = calc_stats["sub_total"]
        
    if not parse_float(final_json.get("taxable_value")):
        logger.info(f"Solver Healing: taxable_value filled from math -> {calc_stats['taxable_value']}")
        final_json["taxable_value"] = calc_stats["taxable_value"]

    if not parse_float(final_json.get("total_sgst")) and not parse_float(final_json.get("total_cgst")):
        # If GST is missing, try to use the calculated one
        gst_split = round(calc_stats["total_gst"] / 2, 2)
        if gst_split > 0:
            logger.info(f"Solver Healing: GST filled from math -> SGST/CGST {gst_split}")
            final_json["total_sgst"] = gst_split
            final_json["total_cgst"] = gst_split
        
    if not parse_float(final_json.get("Stated_Grand_Total")) and not parse_float(final_json.get("grand_total")):
        logger.info(f"Solver Healing: Grand Total filled from math -> {calc_stats['grand_total']}")
        final_json["Stated_Grand_Total"] = calc_stats["grand_total"]
        final_json["grand_total"] = calc_stats["grand_total"]
    
    # --- SMART INVERSE SOLVING (The "Robustness" Layer) ---
    # If we have Grand Total and Sub-Total, but Discount is missing or 0, infer it.
    curr_sub = parse_float(final_json.get("sub_total"))
    curr_grand = parse_float(final_json.get("Stated_Grand_Total") or final_json.get("grand_total"))
    curr_gst = parse_float(final_json.get("total_sgst") or 0) * 2
    curr_disc = parse_float(final_json.get("global_discount"))
    
    if curr_grand > 0 and curr_sub > 0 and curr_disc == 0:
        # Expected = Sub - Disc + Tax
        # Actually: Disc = Sub + Tax - Grand
        implied_disc = round(curr_sub + curr_gst - curr_grand, 2)
        # Only apply if it's a "reasonable" positive discount (e.g. up to 15% of subtotal or large enough to not be roundoff)
        if implied_disc > 0.5: 
             logger.info(f"Solver Robustness: Inferred Global Discount of {implied_disc} from {curr_sub} -> {curr_grand}")
             final_json["global_discount"] = implied_disc
             final_json["Logic_Note"] = final_json.get("Logic_Note", "") + f" [Inferred Disc {implied_disc}]"

    return {
        "line_items": updated_lines, 
        "final_output": final_json 
    }