from prometheus_client import Counter, Gauge
from typing import Dict, Any, List
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.api.metrics import circuit_breaker_tripped_total, invoice_extraction_retries_total

logger = get_logger("critic")

async def critique_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Critic Node.
    Compares Line Item Sum vs. Grand Total Anchor.
    Determines if the invoice is Net-based, Gross-based, or Discount-based.
    """
    logger.info("Critic: Starting extraction critique...")
    
    # 1. Get Extracted Totals
    lines = state.get("line_items") or state.get("line_item_fragments", [])
    
    # Calculate Anchor (Header/Footer Truth)
    anchor_curr = state.get("global_modifiers", {}).get("Stated_Grand_Total", 0.0)
    if not anchor_curr:
        anchor_curr = state.get("anchor_totals", {}).get("Stated_Grand_Total", 0.0)
        
    try:
        anchor_total = float(anchor_curr)
    except:
        anchor_total = 0.0
    
    # Common helper for RETRY_OCR response
    def retry_response(reason: str, error_type: str = "general_fault"):
        invoice_extraction_retries_total.inc()
        current_total = state.get("retry_count", 0) + 1
        return {
            "critic_verdict": "RETRY_OCR",
            "feedback_logs": [reason],
            "retry_count": 1, # Increments state due to operator.add
            "error_metadata": {"last_error": error_type, "total_attempts": current_total}
        }

    # 1.5 - SELF-HEALING LOOP: Check for Column Swap Flag from Auditor
    if state.get("column_swap_mrp"):
        logger.warning("Critic: Auditor flagged a SUSPECTED COLUMN SWAP. Requesting self-correction.")
        return retry_response(
            reason="CRITICAL: You swapped the MRP and Rate columns. The current MRP is mathematically too low for this product to be plausible. Re-examine the image, identify the true MRP column (which is typically the highest unit price), and try again.",
            error_type="column_swap_retry"
        )

    if not lines:
        logger.warning("Critic: Missing lines. Requesting RETRY.")
        return retry_response("Extraction yielded 0 items. Retry with Full Page Scan.", "missing_lines")

    if anchor_total <= 0:
        logger.warning("Critic: Missing anchor total. Passing with warning.")
        return {"critic_verdict": "PASS_WITH_WARNING"} 

    # 2. Calculate Line Sum
    line_sum = 0.0
    debug_vals = []
    zero_mrp_count = 0
    zero_rate_count = 0
    total_items = len(lines)
    
    for i, item in enumerate(lines):
        try:
             val = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
             line_sum += val
             debug_vals.append((item.get("Product"), val))
             mrp = float(item.get("MRP") or 0)
             rate = float(item.get("Rate") or 0)
             if mrp == 0: zero_mrp_count += 1
             if rate == 0: zero_rate_count += 1
        except:
             pass
    
    logger.info(f"Critic: ALL Items: {debug_vals}")
    
    # 3. COLUMN HEALTH CHECK
    if total_items > 0:
        if (zero_mrp_count / total_items) > 0.5:
            logger.warning(f"Critic: Critical Data Fault. {zero_mrp_count}/{total_items} items missing MRP.")
            return retry_response("CRITICAL FAULT: You missed the 'MRP' column. Look for headers like 'MRP' and capture them.", "missing_mrp_column")
            
    # 4. Calculate Ratio
    if line_sum == 0: 
        logger.warning("Critic: Line Sum is 0. Requesting Retry.")
        return retry_response("Line Sum is 0. Please re-extract item amounts carefully.", "zero_sum")
    
    ratio = anchor_total / line_sum
    diff_percent = abs(1 - ratio) * 100

    if diff_percent < 1.0:
        logger.info(f"Critic: Match Exact (or close). APPROVE.")
        return {
            "critic_verdict": "APPROVE", 
            "correction_factor": 1.0
        } 
        
    elif ratio > 1.0 and ratio < 1.30:
        logger.info(f"Critic: Under-sum detected. Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKUP", "correction_factor": ratio} 
        
    elif ratio < 1.0 and ratio > 0.70:
        logger.info(f"Critic: Over-sum detected. Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKDOWN", "correction_factor": ratio} 
        
    else:
        # Massive mismatch (>30%)
        logger.warning(f"Critic: Massive mismatch ({diff_percent:.2f}%). RETRY_OCR.")
        if line_sum < anchor_total:
            missing_val = anchor_total - line_sum
            feedback_msg = f"Validation Failed: Extracted Total ({line_sum:.2f}) < Invoice Total ({anchor_total:.2f}). Missing approx {missing_val:.2f}."
        else:
            excess_val = line_sum - anchor_total
            feedback_msg = f"Validation Failed: Extracted Total ({line_sum:.2f}) > Invoice Total ({anchor_total:.2f}). Hallucinated approx {excess_val:.2f}."
        
        # PROMETHEUS: If we are hitting a high number of retries (e.g. 5 total loops), circuit breaker is prepped.
        current_total = state.get("retry_count", 0) + 1
        if current_total >= 5:
            circuit_breaker_tripped_total.inc()
            logger.warning(f"Critic: Circuit breaker triggered after {current_total} attempts.")

        res = retry_response(feedback_msg, "math_mismatch")
        res["error_history"] = [f"Math Mismatch: {diff_percent:.2f}% (Attempt {current_total})"]
        return res
