from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.api.metrics import invoice_healer_triggered_total, invoice_unreconciled_value
from langfuse import observe
from src.services.langfuse_client import langfuse_manager

logger = get_logger("solver")

@observe(name="math_solver")
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
    recon_stats = {
        "initial_gap": round(gap, 2),
        "mode": mode,
        "healer_active": False
    }
    
    # Adjust stated_total if it seems to be missing the Credit Note adjustment
    # (i.e. if the gap to the stated total is exactly the credit note)
    cn_amount = initial_stats.get("credit_note_amount", 0.0)
    gap_if_pre_cn = abs(initial_calc_total + cn_amount - stated_total)
    
    if gap_if_pre_cn < 2.0 and cn_amount > 0:
        logger.info(f"Solver: Gap {gap:.2f} explained by Stated Total being Pre-Credit Note. No correction factor needed.")
        correction_factor = 1.0
        gap = gap_if_pre_cn
    elif gap > 2.0 and stated_total > 0 and initial_calc_total > 0:
        # Formula: (Stated / Initial_Calc) - Apply to all line items proportionally
        correction_factor = stated_total / initial_calc_total
        logger.info(f"Solver: Unexplained gap {gap:.2f} (Mode: {mode}). Calculated correction factor {correction_factor:.4f}")
        
        # PROMETHEUS: Track the financial gap of this "broken" invoice
        invoice_unreconciled_value.set(gap)
        recon_stats["tolerance_breached"] = True
        
        # NOTE: Scoring from within nodes in v3 requires OTel context. 
        # Skipping scoring for now to ensure backend starts successfully.
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
            # --- PRE-MAPPING (Always show text even if math fails) ---
            item["Standard_Item_Name"] = item.get("Standard_Item_Name") or item.get("Product") or "Unknown Item"
            item["Batch_No"] = item.get("Batch_No") or item.get("Batch") or "N/A"
            item["Expiry_Date"] = item.get("Expiry_Date") or item.get("Expiry") or "N/A"
            item["Pack_Size_Description"] = item.get("Pack_Size_Description") or item.get("Pack") or "Unit"
            
            # Use robust quantity parser (handles "10+2", "10 Pcs", etc.)
            from src.domain.normalization.financials import parse_quantity
            qty = parse_quantity(item.get("Qty"), item.get("Free") or 0)
            item["Standard_Quantity"] = qty
            
            # Apply correction factor ONLY if it's within a very strict tolerance (3%)
            # and if the gap wasn't already explained by a Credit Note or missing tax
            diag_str = f" [Gap:{gap:.2f}/CF:{correction_factor:.4f}]"
            
            # Use stricter tolerance for scaling to avoid "inflation"
            if 0.98 <= correction_factor <= 1.02 and not recon_stats.get("healer_active"):
                 raw_net = float(item.get("Net_Line_Amount") or item.get("Amount") or 0.0)
                 item["Net_Line_Amount"] = round(raw_net * correction_factor, 2)
                 # Re-calculate landing cost with factor
                 item["effective_landing_cost"] = round(item["effective_landing_cost"] * correction_factor, 2)
                 item["Logic_Note"] = (item.get("Logic_Note", "") + f" [Auto-Adjusted {correction_factor:.4f}]{diag_str}").strip()
            else:
                 # If gap is significant (>2%) or already explained, DO NOT SCALE the UI Net Amount.
                 # Only scale the internal landing cost to ensure the ledger balances.
                 item["effective_landing_cost"] = round(item["effective_landing_cost"] * correction_factor, 2)
                 item["Logic_Note"] = (item.get("Logic_Note", "") + f" [Landed Scaled Only]{diag_str}").strip()

            cost_price = item.get("Final_Unit_Cost", 0.0)
            if qty > 0:
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

            # Ensure Net Amount and unit cost are correctly set
            item["Net_Line_Amount"] = item.get("Net_Line_Amount") or item.get("Amount") or 0.0
            
            updated_lines.append(item)
        except Exception as e:
            logger.error(f"Solver Line Error: {e}")
            updated_lines.append(item)
            
    # 5. FINAL HEALING
    final_json = headers.copy()
    final_json["Line_Items"] = updated_lines
    
    # Merge specialized supplier details if available
    supplier_details = state.get("supplier_details", {})
    if supplier_details:
        final_json["supplier_details"] = supplier_details
        
        # Priority mapping for common header fields
        for field in ["Supplier_Name", "Invoice_No", "Invoice_Date", "GSTIN", "Address", "DL_No"]:
            if supplier_details.get(field):
                # Always prioritize the specialized agent's result if the main one is missing or default
                current_val = str(final_json.get(field, "")).strip().lower()
                if not current_val or current_val in ["unknown", "n/a", "none"]:
                    final_json[field] = supplier_details[field]
                    logger.info(f"Solver Header Fix: Set {field} = {supplier_details[field]}")
    
    # Run one final reconciliation pass to ensure footer stats match the corrected items
    final_recon = reconcile_financials(updated_lines, headers, stated_total)
    final_stats = final_recon.get("calculated_stats", {})
    
    final_json["sub_total"] = final_stats.get("sub_total", 0.0)
    final_json["taxable_value"] = final_stats.get("taxable_value", 0.0)
    final_json["round_off"] = final_stats.get("round_off", 0.0)
    final_json["total_sgst"] = final_stats.get("total_sgst", 0.0)
    final_json["total_cgst"] = final_stats.get("total_cgst", 0.0)
    final_json["credit_note_amount"] = final_stats.get("credit_note_amount", 0.0)
    final_json["extra_charges"] = final_stats.get("extra_charges", 0.0)
    final_json["grand_total"] = final_stats.get("grand_total", 0.0)
    final_json["Stated_Grand_Total"] = stated_total
    
    # 6. Final Discount Recovery (Removed to prevent hallucinations)
    # We no longer infer discounts to close gaps.
    pass

    # 7. FINAL AUDIT FLAG (The "Verification Layer" for the User)
    final_json["Extraction_Warnings"] = []
    gap_percent = (gap / stated_total) * 100 if stated_total > 0 else 100
    
    if gap > 2.0:
        warning = f"Calculation Audit: Reconciled Total ₹{final_stats.get('grand_total', initial_calc_total):.2f} differs from Stated ₹{stated_total:.2f}. Please verify."
        final_json["audit_status"] = "WARNING"
        final_json["Extraction_Warnings"].append(warning)
        if gap_percent > 10:
            final_json["audit_status"] = "CRITICAL_FAILURE"
            final_json["Extraction_Warnings"].append("CRITICAL: Major financial mismatch detected. Table extraction may be corrupt.")
    else:
        final_json["audit_status"] = "VERIFIED"

    return {
        "line_items": updated_lines, 
        "final_output": final_json,
        "reconciliation_stats": recon_stats
    }