from typing import Dict, Any
import logging
from src.workflow.state import InvoiceState as InvoiceStateDict

logger = logging.getLogger(__name__)

def critique_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Critic Node.
    Compares Line Item Sum vs. Grand Total Anchor.
    Determines if the invoice is Net-based, Gross-based, or Discount-based.
    """
    logger.info("Critic: Starting extraction critique...")
    
    # 1. Get the Data
    lines = state.get("line_item_fragments", [])
    # Ensure Anchor agent saved 'Stated_Grand_Total' into global_modifiers or anchor_totals
    # User requested global_modifiers access, checking both for robustness
    anchor_curr = state.get("global_modifiers", {}).get("Stated_Grand_Total", 0.0)
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
    for item in lines:
        try:
             val = float(item.get("Stated_Net_Amount") or 0)
             line_sum += val
        except:
             pass
    
    # 3. Calculate Ratio (The "Magic Number")
    logger.info(f"Critic: Anchor {anchor_total} vs Line Sum {line_sum}")
    
    if line_sum == 0: 
        return {"critic_verdict": "RETRY_EXTRACTION"}
    
    ratio = anchor_total / line_sum
    diff_percent = abs(1 - ratio) * 100

    # 4. Universal Decision Matrix
    if diff_percent < 1.0:
        logger.info("Critic: Match Exact (or close). APPROVE.")
        return {"critic_verdict": "APPROVE"} # C.M. Associates (Exact match)
        
    elif ratio > 1.0 and ratio < 1.30:
        # Sum is LESS than Total (e.g. 875 vs 920). 
        # This implies Global Tax or Freight was added at the bottom.
        logger.info(f"Critic: Under-sum detected (Markup needed). Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKUP", "correction_factor": ratio} # Deepak Agencies
        
    elif ratio < 1.0 and ratio > 0.70:
        # Sum is MORE than Total.
        # This implies Global Discount was subtracted at the bottom.
        logger.info(f"Critic: Over-sum detected (Markdown needed). Ratio {ratio:.4f}")
        return {"critic_verdict": "APPLY_MARKDOWN", "correction_factor": ratio} # Enn Pee Medical
        
    else:
        # Massive mismatch (>30%). Likely a bad OCR scan or missing rows.
        logger.warning(f"Critic: Massive mismatch ({diff_percent:.2f}%). RETRY_OCR.")
        return {"critic_verdict": "RETRY_OCR"}
