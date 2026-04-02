import math
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.domain.normalization import parse_float
from src.domain.constants import BLACKLIST_KEYWORDS, AUDITOR_CONFIG, SCHEME_PATTERNS
from src.services.ai_client import manager
from src.services.mistake_memory import MEMORY
from src.utils.ai_retry import ai_retry

logger = get_logger("auditor")

@ai_retry
async def llm_hallucination_cleanup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rules_list = MEMORY.get_rules()
    memory_rules = "\n    ".join([f"- {r}" for r in rules_list]) if rules_list else "- No previous mistakes recorded."

    prompt = f"""
    You are an Expert Pharmacy Data Auditor.
    I am giving you a JSON array of invoice line items mapped by an AI.
    Your task is to CLEAN UP these items logically BEFORE they undergo programmatic deduplication.

    CRITICAL RULES TO FOLLOW (Learned from mistakes.json):
    {memory_rules}

    Return the cleaned items as a valid JSON array. Do not remove any items unless instructed by the rules.
    Use the exact same schema.

    Raw Extracted Items:
    {json.dumps(items, indent=2)}
    
    Output format:
    [
        {{ ...item... }},
        {{ ...item... }}
    ]
    """
    
    try:
        response = await manager.generate_content_async(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        text = response.text.strip().replace("```json", "").replace("```", "")
        cleaned_items = json.loads(text)
        
        if isinstance(cleaned_items, dict):
            for k, v in cleaned_items.items():
                if isinstance(v, list):
                    return v
        if isinstance(cleaned_items, list):
            return cleaned_items
        return items
    except Exception as e:
        logger.error(f"Auditor LLM Cleanup Failed: {e}")
        return items

async def audit_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Auditor Node.
    performs a textual/math verification pass to catch logical errors
    like 'Double Tax' (Net vs Taxable) or missing Global Discounts.
    """
    image_path = state.get("image_path")
    line_items = state.get("line_item_fragments", [])
    global_modifiers = state.get("global_modifiers", {})
    
    if not image_path or not line_items:
        return {"error_logs": ["Auditor: Missing input data."]}

    # --- LLM CLEANUP PASS ---
    logger.info("Auditor: Initiating LLM hallucination cleanup based on mistakes.json...")
    line_items = await llm_hallucination_cleanup(line_items)

    # --- PHASE 3: THE AGGREGATION "CLUBBING" ENGINE ---
    # Rule: If Product and Batch match, SUM them.
    aggregated_map = {}
    
    for item in line_items:
        try:
            # 1. Noise & Blacklist Filter
            n_val = parse_float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            q_val = parse_float(item.get("Qty") or 0)
            f_val = parse_float(item.get("Free") or 0)
            has_batch = item.get("Batch") and str(item.get("Batch")).lower() not in ["", "none", "n/a", "null"]
            
            if abs(n_val) < AUDITOR_CONFIG['NOISE_THRESHOLD'] and abs(q_val) < AUDITOR_CONFIG['NOISE_THRESHOLD'] and not has_batch:
                continue
                
            desc_raw = str(item.get("Product", "") or item.get("Description", ""))
            desc_lower = desc_raw.lower()
            if any(bad_word in desc_lower for bad_word in BLACKLIST_KEYWORDS):
                logger.info(f"Auditor: Dropping Blacklisted Item '{desc_lower}'")
                continue

            # 1b. HEURISTIC UN-CLUBBING (Batch from Description)
            # If batch is missing but description contains "B.No", "Batch", "Lot" or uppercase code
            if not has_batch:
                # Look for common batch patterns at the end of description
                # Pattern: " ... B.No: A123" or " ... (Batch: A123)" or " ... A123" (where A123 is uppercase alphanumeric)
                import re
                batch_match = re.search(r'(?:batch|b\.?no|lot)[:\s\-]+([A-Z0-9]{4,15})', desc_raw, re.IGNORECASE)
                if not batch_match:
                     # Fallback: Check for trailing uppercase alphanumeric block if it's distinct
                     tokens = desc_raw.split()
                     if len(tokens) > 1:
                          last_token = tokens[-1]
                          if len(last_token) >= 4 and last_token.isupper() and any(c.isdigit() for c in last_token):
                               item["Batch"] = last_token
                               item["Product"] = " ".join(tokens[:-1])
                               logger.info(f"Auditor: Un-clubbed Batch '{last_token}' from Product name.")
                else:
                    batch_val = batch_match.group(1)
                    item["Batch"] = batch_val
                    # Clean the product name
                    item["Product"] = desc_raw.replace(batch_match.group(0), "").strip()
                    logger.info(f"Auditor: Un-clubbed Batch '{batch_val}' from Product (via keyword).")
                
                # Update has_batch after attempt
                has_batch = item.get("Batch") and str(item.get("Batch")).lower() not in ["", "none", "n/a", "null"]

            # 2. Decimal Fix (Self-Healing)
            if n_val > 10000 and q_val < 100:
                logger.warning(f"Auditor: Decimal Error in Amount {n_val}. Correcting.")
                n_val /= 100
                item["Amount"] = n_val
                item["Logic_Note"] = item.get("Logic_Note", "") + " [Decimal Fix]"

            # 2a. RETURN ITEM DETECTION (New Feature)
            # If item name contains "RETURN", negate the amount to ensure sum is correct
            is_return_keyword = any(k in desc_lower for k in ["return", "cr note", "credit note", "less", "cr.note"])
            if is_return_keyword:
                logger.info(f"Auditor: Detected return item '{desc_lower}'. Negating amount.")
                n_val = -abs(n_val) # Ensure it's negative
                q_val = -abs(q_val)
                item["Amount"] = n_val
                item["Qty"] = q_val
                item["Is_Return"] = True
                item["Logic_Note"] = (item.get("Logic_Note", "") + " [Return Item - Negated]").strip()
            
            # 3. Create Aggregation Key (Product + Batch)
            # Use raw description but standardized tokens
            p_key = " ".join(str(item.get("Product", "")).strip().lower().split())
            
            # Batch Normalization
            raw_batch = str(item.get("Batch") or "N/A").strip().lower()
            for prefix in ["batch", "no", "lot", "b.no", "bno", ".", ":", "-"]:
                raw_batch = raw_batch.replace(prefix, "")
            b_key = raw_batch.replace(" ", "")
            if b_key in ["", "none", "null", "n/a", "unknown"]:
                b_key = "unknown_batch"
            
            agg_key = f"{p_key}|{b_key}"
            
            if agg_key in aggregated_map:
                existing = aggregated_map[agg_key]
                logger.info(f"Auditor: Clubbing duplicate item '{p_key}' Batch '{b_key}'")
                
                # Sum Quantities and Amounts
                existing_qty = parse_float(existing.get("Qty", 0))
                existing_free = parse_float(existing.get("Free", 0))
                existing_amt = parse_float(existing.get("Amount", 0))
                
                existing["Qty"] = existing_qty + q_val
                existing["Free"] = existing_free + f_val
                existing["Amount"] = existing_amt + n_val
                
                # Logic Note
                existing["Logic_Note"] = (existing.get("Logic_Note", "") + f" [Clubbed Qty +{q_val}]").strip()
                
                # Preserve largest Rate/MRP if they differ (rare)
                existing["Rate"] = max(parse_float(existing.get("Rate", 0)), parse_float(item.get("Rate", 0)))
                existing["MRP"] = max(parse_float(existing.get("MRP", 0)), parse_float(item.get("MRP", 0)))
            else:
                # Add new entry
                item["Qty"] = q_val
                item["Free"] = f_val
                item["Amount"] = n_val
                aggregated_map[agg_key] = item

        except Exception as e:
            logger.warning(f"Auditor Aggregation Error: {e}")
            # Fallback: append if failed to parse
            aggregated_map[f"error_{len(aggregated_map)}"] = item

    deduped_line_items = list(aggregated_map.values())
    logger.info(f"Auditor: Clubbing: Reduced {len(line_items)} items to {len(deduped_line_items)} unique entries.")
    # ---------------------------------------------------
    
    # 7. Robust Quantity Reconstruction (Math as Source of Truth)
    # Replaces specific "Swap Fixes" with a general rule: Qty = Amount / Rate
    deduped_line_items = _reconcile_quantities_with_math(deduped_line_items)

    logger.info("Auditor verification complete.")
    
    # SANITIZE GLOBAL MODIFIERS
    # Ensure Discount/Freight/Tax are positive (absolute values) to prevent double-negatives in Frontend/Solver
    cleaned_modifiers = global_modifiers.copy()
    for key in ["Global_Discount_Amount", "Freight_Charges", "Global_Tax_Amount"]:
        if key in cleaned_modifiers and cleaned_modifiers[key]:
             try:
                 val = float(cleaned_modifiers[key])
                 # Take absolute value. 
                 # If OCR reads "-33.00", we want 33.00 (as 'Discount' implies subtraction).
                 if val < 0:
                     logger.warning(f"Auditor: Sanitizing Negative Modifier {key}={val} -> {abs(val)}")
                 
                 cleaned_modifiers[key] = abs(val)
             except:
                 pass
    
    # 6. PRICE PLAUSIBILITY CHECK (Self-Healing)
    # Check for Column Swap: MRP <= Rate (Invalid in retail pharmacy)
    swap_detected = False
    swap_count = 0
    valid_p_count = 0
    for item in deduped_line_items:
        try:
            m_val = parse_float(item.get("MRP") or 0)
            r_val = parse_float(item.get("Rate") or 0)
            if m_val > 0 and r_val > 0:
                valid_p_count += 1
                if m_val <= r_val: # Should be MRP > Rate
                    swap_count += 1
        except: pass
    
    if valid_p_count > 0 and (swap_count / valid_p_count) > 0.3: # > 30% Mismatch
        logger.warning(f"Auditor: SUSPECTED COLUMN SWAP! ({swap_count}/{valid_p_count} items have MRP <= Rate)")
        swap_detected = True

    # Strict Python list comprehension to purge invalid items and nulls
    cleaned_items = [
        item for item in deduped_line_items
        if item is not None and isinstance(item, dict) and (item.get('name') or item.get('Product') or item.get('Standard_Item_Name') or item.get('Amount') or item.get('Net_Line_Amount'))
    ]

    return {
        "line_items": cleaned_items, 
        "global_modifiers": cleaned_modifiers,
        "column_swap_mrp": swap_detected
    }

def _reconcile_quantities_with_math(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enforces the invariant: Quantity * Rate = Amount.
    
    UPDATED STRATEGY (Robust Ambiguity Resolution):
    1. If Qty matches Amount/Rate perfectly, Keep it.
    2. If Qty = 1 BUT Amount / Rate ~= 2, 3, 4... -> TRUST MATH. (Fix Qty).
       - This handles cases where OCR returns empty Qty and Mapper defaults to 1.
    3. If Qty > 1 and mismatch exists -> TRUST QTY. (Fix Rate).
    4. If Qty is missing/zero -> CALCULATE Qty.
    """
    for item in items:
        try:
            qty_extracted = float(item.get("Qty") or 0)
            rate = float(item.get("Rate") or 0)
            amt = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            
            # 1. Sanity Check: If Amount/Rate missing, skip
            if amt <= 0.1 or rate <= 0.1:
                continue

            # 2. Check for "The Default 1.0 Hallucination"
            # Scenario: Mapper sees empty column, puts 1.0. 
            # Real Life: Rate=100, Amount=200. Implies Qty=2.
            # Old Logic: Resets Rate to 200/1 = 200. (WRONG)
            # New Logic: Sets Qty to 200/100 = 2. (CORRECT)
            
            calc_qty = amt / rate
            is_integer_qty = abs(calc_qty - round(calc_qty)) < 0.05
            implied_qty = round(calc_qty)
            
            # If Extracted is 1.0, but Math strongly suggests a different Integer > 1
            if 0.9 < qty_extracted < 1.1 and implied_qty > 1 and is_integer_qty:
                 logger.info(f"Auditor: Qty 1.0 detected but Math implies Qty {implied_qty} (Amt {amt} / Rate {rate}). Correcting Qty.")
                 item["Qty"] = float(implied_qty)
                 item["Logic_Note"] = item.get("Logic_Note", "") + " [Math-Corrected Qty]"
                 continue # Done with this item
            
            # 3. Standard Mismatch Check
            expected_amt = qty_extracted * rate
            is_mismatch = abs(expected_amt - amt) > max(2.0, amt * 0.05)
            
            if is_mismatch:
                # CASE A: OCR Qty Exists (> 1 or non-integer 1 that wasn't caught above) -> Trust Qty, Fix Rate
                if qty_extracted > 0.1:
                    new_rate = amt / qty_extracted
                    logger.info(f"Auditor: Math Mismatch for '{item.get('Product')}'. Trusting OCR Qty {qty_extracted}. Adjusting Rate {rate} -> {new_rate:.2f}")
                    item["Rate"] = new_rate
                    item["Logic_Note"] = item.get("Logic_Note", "") + " [Rate Fix]"
                
                # CASE B: OCR Qty Missing -> Trust Rate, Fix Qty
                elif rate > 0.1:
                     final_qty = round(calc_qty) 
                     if final_qty < 1: final_qty = 1
                     
                     logger.info(f"Auditor: Missing Qty for '{item.get('Product')}'. Calculated {final_qty} from Amt {amt} / Rate {rate}")
                     item["Qty"] = float(final_qty)
                     item["Logic_Note"] = item.get("Logic_Note", "") + " [Calc Qty]"

        except Exception as e:
            logger.warning(f"Auditor Math Error: {e}")
            continue
            
    return items
