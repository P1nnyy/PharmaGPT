from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("solver")

def apply_correction(state: InvoiceStateDict) -> Dict[str, Any]:
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
    
    return {
        "line_items": updated_lines, 
        "final_output": final_json 
    }