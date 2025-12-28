from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

logger = get_logger("critic")

def critique_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Critic Node.
    Compares Line Item Sum vs. Grand Total Anchor.
    Determines if the invoice is Net-based, Gross-based, or Discount-based.
    """
    logger.info("Critic: Starting extraction critique...")
    
    # 1. Get Extracted Totals
    # PREFER: Cleaned 'line_items' from Auditor
    # FALLBACK: 'line_item_fragments' from Worker (Dirty/Duplicate)
    lines = state.get("line_items") or state.get("line_item_fragments", [])
    
    # Calculate Anchor (Header/Footer Truth)
    # Ensure Anchor agent saved 'Stated_Grand_Total' into global_modifiers or anchor_totals
    # User requested global_modifiers access, checking both for robustness
    anchor_curr = state.get("global_modifiers", {}).get("Stated_Grand_Total", 0.0)
    
    # NEW: Row Count Estimation (from Surveyor)
    estimated_rows = 0
    extraction_plan = state.get("extraction_plan", [])
    for zone in extraction_plan:
        if zone.get("type") == "primary_table" and zone.get("estimated_row_count"):
            estimated_rows += int(zone.get("estimated_row_count"))
            
    logger.info(f"Critic: Estimated Rows from Surveyor: {estimated_rows}")
    if estimated_rows == 0:
        logger.warning("Critic: No Estimated Row Count found. Hallucination Check 3 will be skipped.")
            
    if not anchor_curr:
        anchor_curr = state.get("anchor_totals", {}).get("Stated_Grand_Total", 0.0)
        
    try:
        anchor_total = float(anchor_curr)
    except:
        anchor_total = 0.0
    
    if not lines or anchor_total <= 0:
        logger.warning("Critic: Missing lines or anchor total. Passing with warning.")
        return {"critic_verdict": "PASS_WITH_WARNING"} # Fail open

    # 2. Calculate Line Sum
    line_sum = 0.0
    debug_vals = []
    
    # METADATA HEALTH CHECKS
    zero_mrp_count = 0
    zero_rate_count = 0
    total_items = len(lines)
    
    for i, item in enumerate(lines):
        try:
             # UPDATED: Use Amount (Blind Schema)
             val = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
             line_sum += val
             debug_vals.append((item.get("Product"), val))
             
             # Health Check Stats
             mrp = float(item.get("MRP") or 0)
             rate = float(item.get("Rate") or 0)
             
             if mrp == 0: zero_mrp_count += 1
             if rate == 0: zero_rate_count += 1
             
        except:
             pass
    
    logger.info(f"Critic: ALL Items: {debug_vals}")
    
    # 3. COLUMN HEALTH CHECK (Prioritize Data Quality over Totals)
    # If > 50% of items are missing MRP, FAIL immediately.
    if total_items > 0:
        # CHECK 1: Missing Product Names (Blocking)
        missing_names = [item for item in lines if not item.get("Product") or item.get("Product") == "None"]
        if missing_names:
            logger.warning(f"Critic: Found {len(missing_names)} items with MISSING PRODUCT NAMES.")
            # Construct specific feedback
            bad_values = [str(item.get("Amount", "Unknown")) for item in missing_names]
            return {
                "critic_verdict": "RETRY_OCR",
                "feedback_logs": [f"CRITICAL FAULT: You extracted items with amounts {bad_values} but missed the 'Product' Description. You MUST extract the Product Name for every row."]
            }

        if (zero_mrp_count / total_items) > 0.5:
            logger.warning(f"Critic: Critical Data Fault. {zero_mrp_count}/{total_items} items missing MRP.")
            return {
                "critic_verdict": "RETRY_OCR",
                "feedback_logs": ["CRITICAL FAULT: You missed the 'MRP' column. The user requires MRP extraction. Look for headers like 'MRP', 'Max Price', 'Rate' and capture them."]
            }
            
        # CHECK 2: Duplicates Check (Post-Auditor)
        # If Auditor missed them, and Sum > Anchor, we have a problem.
        seen_sigs = set()
        duplicates = []
        for item in lines:
            # Signature: Name + Amount
            sig = (str(item.get("Product")).strip().lower(), float(item.get("Amount") or 0))
            if sig in seen_sigs:
                duplicates.append(item.get("Product"))
            else:
                seen_sigs.add(sig)
        
        # We only flag duplicates if the Numbers don't match. 
        # If Sum == Anchor, duplicates might be valid (e.g. 2x same item billed).
        # But we check this in the Ratio logic below.
        
    # CHECK 3: Hallucination / Row Count Mismatch (User Complaint: 13 rows -> 25 extracted)
    if total_items > 5 and estimated_rows > 0:
        # Threshold: If extracted is > 1.5x Estimated.
        # e.g. Est 13 -> Max 19. If 25 -> RETRY.
        if total_items > (estimated_rows * 1.5):
            logger.warning(f"Critic: Row Count Mismatch! Extracted {total_items} vs Estimated {estimated_rows}.")
            return {
                "critic_verdict": "RETRY_OCR",
                "feedback_logs": [f"CRITICAL: You extracted {total_items} items, but the document only seems to have approx {estimated_rows}. You are likely Hallucinating/Splitting rows. MERGE multi-line descriptions."]
            }
            
    # CHECK 4: Under-Extraction Check
    # If Extracted count is significantly LESS than Estimated (e.g. 13 Est -> 8 Extracted), it's a miss.
    if estimated_rows > 3 and total_items < (estimated_rows * 0.8):
        logger.warning(f"Critic: Under-Extraction! Extracted {total_items} vs Estimated {estimated_rows}.")
        return {
            "critic_verdict": "RETRY_OCR",
            "feedback_logs": [f"CRITICAL: You only extracted {total_items} items, but the document seems to have approx {estimated_rows}. You missed rows. Check for dense rows or low-contrast text."]
        }
            
    # 4. Calculate Ratio (The "Magic Number")
    logger.info(f"Critic: Anchor {anchor_total} vs Line Sum {line_sum}")
    
    if line_sum == 0: 
        logger.warning("Critic: Line Sum is 0. Requesting Retry.")
        return {"critic_verdict": "RETRY_OCR"}
    
    ratio = anchor_total / line_sum
    diff_percent = abs(1 - ratio) * 100

    # 4. Universal Decision Matrix
    # 4. Universal Decision Matrix
    feedback_msg = ""
    
    # NEW: If Duplicates exist AND Sum > Total (Over-sum), it's definitely a duplication error.
    if duplicates and ratio < 0.99:
         logger.warning(f"Critic: Duplicates Detected {duplicates} and Over-sum. RETRY.")
         return {
            "critic_verdict": "RETRY_OCR",
            "feedback_logs": [f"CRITICAL ERROR: You extracted duplicate items {duplicates} which caused the Total to exceed the Invoice Value. Remove duplicates."]
         }
    
    if diff_percent < 0.1:
        logger.info(f"Critic: Match Exact (within 0.1%). APPROVE.")
        
        # On APPROVE, we must Construct Final Output (Headers + Lines)
        # because we skip the Solver node.
        headers = state.get("global_modifiers", {})
        final_output = headers.copy()
        final_output["Line_Items"] = lines
        
        return {
            "critic_verdict": "APPROVE", 
            "correction_factor": 1.0,
            "final_output": final_output
        } 
        
    # Check for Global Modifiers presence to confirm intent
    g_mods = state.get("global_modifiers", {})
    has_discount = float(g_mods.get("Global_Discount_Amount") or 0) > 0
    
    if has_discount and ratio < 1.0:
         logger.info(f"Critic: Global Discount Detected + Over-sum (Ratio {ratio:.4f}). Sending to Solver.")
         return {"critic_verdict": "APPLY_MARKDOWN", "correction_factor": ratio}

    elif ratio > 1.0 and ratio < 1.30:
        # Sum is LESS than Total (e.g. 875 vs 920). 
        # This implies Global Tax or Freight was added at the bottom.
        logger.info(f"Critic: Under-sum detected (Markup needed). Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKUP", "correction_factor": ratio} 
        
    elif ratio < 1.0 and ratio > 0.70:
        # Sum is MORE than Total.
        # This implies Global Discount was subtracted at the bottom.
        logger.info(f"Critic: Over-sum detected (Markdown needed). Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKDOWN", "correction_factor": ratio} 
        
    else:
        # Massive mismatch (>30%). Likely a bad OCR scan or missing rows.
        logger.warning(f"Critic: Massive mismatch ({diff_percent:.2f}%). RETRY_OCR.")
        
        # GENERATE SMART FEEDBACK
        if line_sum < anchor_total:
            missing_val = anchor_total - line_sum
            feedback_msg = (
                f"Validation Failed: Extracted Total ({line_sum:.2f}) is significantly LOWER than Invoice Total ({anchor_total:.2f}). "
                f"You are missing items worth approx {missing_val:.2f}. "
                "Check for missed rows at bottom of table or tax rows misidentified."
            )
        else:
            excess_val = line_sum - anchor_total
            feedback_msg = (
                f"Validation Failed: Extracted Total ({line_sum:.2f}) is significantly HIGHER than Invoice Total ({anchor_total:.2f}). "
                f"You have hallucinated approx {excess_val:.2f}. "
                "Check if you accidentally extracted 'Total' or 'Subtotal' rows as line items."
            )
            
        return {
            "critic_verdict": "RETRY_OCR",
            "feedback_logs": [feedback_msg]
        }
