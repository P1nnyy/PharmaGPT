from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.api.metrics import invoice_healer_triggered_total, invoice_unreconciled_value

logger = get_logger("solver")

async def apply_correction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Solver Node.
    1. Detects Calculation Mode (Line-Level vs Global).
    2. Applies logic-based reconciliation to minimize 'Double Tax' or 'Missing Discount' errors.
    3. Auto-calculates Sales Rates based on reconciled Landed Cost.
    """
    lines = state.get("line_items") or state.get("line_item_fragments", [])
    headers = state.get("global_modifiers", {})
    
    from src.domain.normalization.financials import reconcile_financials, parse_float
    
    stated_total = parse_float(headers.get("Stated_Grand_Total") or headers.get("grand_total") or 0.0)

    # 1. INITIAL PASS: Try to explain the gap without any correction
    initial_recon = reconcile_financials(lines, headers, stated_total)
    mode = initial_recon.get("mode", "GLOBAL")
    initial_stats = initial_recon.get("calculated_stats", {})
    initial_calc_total = initial_stats.get("grand_total", 0.0)
    
    gap = abs(initial_calc_total - stated_total)
    correction_factor = 1.0
    
    # 2. DECISION: Do we need a correction factor?
    # If gap is > 2.0 across both modes, we calculate a correction factor to force match.
    recon_stats = {
        "initial_gap": round(gap, 2),
        "mode": mode,
        "healer_active": False
    }

    if gap > 2.0 and stated_total > 0 and initial_calc_total > 0:
        # Formula: (Stated / Initial_Calc) - Apply to all line items proportionally
        correction_factor = stated_total / initial_calc_total
        logger.info(f"Solver: Unexplained gap {gap:.2f} (Mode: {mode}). Calculated correction factor {correction_factor:.4f}")
        
        # PROMETHEUS: Track the financial gap of this "broken" invoice
        invoice_unreconciled_value.set(gap)
        recon_stats["tolerance_breached"] = True
    else:
        logger.info(f"Solver: Gap {gap:.2f} explained by {mode} logic. No correction factor needed.")
        # PROMETHEUS: If we are in GLOBAL mode and the gap was explained, the "Healer" worked
        if mode == "GLOBAL":
            invoice_healer_triggered_total.inc()
            recon_stats["healer_active"] = True
        invoice_unreconciled_value.set(0) # Reset on success

    # 3. APPLY RECONCILED DATA & CALCULATE RATES
    updated_lines = []
    # Use the items from the initial_recon as they already have effective_landing_cost
    for item in initial_recon.get("line_items", []):
        try:
            qty = float(item.get("Qty") or 1)
            
            # Apply correction factor if verified needed
            if correction_factor != 1.0:
                 raw_net = float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0)
                 item["Net_Line_Amount"] = round(raw_net * correction_factor, 2)
                 # Re-calculate landing cost with factor
                 item["effective_landing_cost"] = round(item["effective_landing_cost"] * correction_factor, 2)
                 item["Logic_Note"] = (item.get("Logic_Note", "") + f" [Auto-Adjusted {correction_factor:.4f}]").strip()

            cost_price = item.get("Final_Unit_Cost", 0.0)
            if correction_factor != 1.0 and qty > 0:
                 cost_price = round(item["effective_landing_cost"] / qty, 2)
                 item["Final_Unit_Cost"] = cost_price

            # Verify Product Name
            if not item.get("Product") or str(item.get("Product")).lower() == "none":
                 item["Product"] = "Unknown Item"

            # 4. SALES RATE LOGIC
            mrp = float(item.get("MRP") or 0)
            if mrp > 0:
                item["Sales_Rate_A"] = mrp
                item["Sales_Rate_B"] = round(mrp * 0.90, 2)
                item["Sales_Rate_C"] = round(mrp * 0.80, 2)
                item["Logic_Note"] += " [Rates: MRP-Based]"
            else:
                item["Sales_Rate_A"] = round(cost_price * 1.50, 2)
                item["Sales_Rate_B"] = round(cost_price * 1.30, 2)
                item["Sales_Rate_C"] = round(cost_price * 1.20, 2)
                item["Logic_Note"] += " [Rates: Cost+Margin]"

            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Line Error: {e}")
            updated_lines.append(item)
            
    # 5. FINAL HEALING
    final_json = headers.copy()
    final_json["Line_Items"] = updated_lines
    # Merge specialized supplier details if available
    supplier_details = state.get("supplier_details")
    if supplier_details:
        final_json["supplier_details"] = supplier_details
    
    # Run one final reconciliation pass to ensure footer stats match the corrected items
    final_recon = reconcile_financials(updated_lines, headers, stated_total)
    final_stats = final_recon.get("calculated_stats", {})
    
    final_json["sub_total"] = final_stats.get("sub_total", 0.0)
    final_json["taxable_value"] = final_stats.get("taxable_value", 0.0)
    final_json["round_off"] = final_stats.get("round_off", 0.0) # Correctly capture discovered round_off
    final_json["total_sgst"] = headers.get("total_sgst") or headers.get("SGST_Amount")
    final_json["total_cgst"] = headers.get("total_cgst") or headers.get("CGST_Amount")
    final_json["grand_total"] = final_stats.get("grand_total", 0.0)
    final_json["Stated_Grand_Total"] = stated_total
    
    # Signify if we inferred a missing discount
    if mode == "GLOBAL" and initial_stats.get("sub_total", 0) > stated_total and parse_float(headers.get("global_discount")) == 0:
         implied_disc = round(initial_stats.get("sub_total", 0) - stated_total, 2)
         if implied_disc > 1.0:
              final_json["Logic_Note"] = final_json.get("Logic_Note", "") + f" [Inferred Disc {implied_disc}]"

    return {
        "line_items": updated_lines, 
        "final_output": final_json,
        "reconciliation_stats": recon_stats
    }