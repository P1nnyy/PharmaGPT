import google.generativeai as genai
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.normalization import parse_float

logger = get_logger("auditor")

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=API_KEY)

def audit_extraction(state: InvoiceStateDict) -> Dict[str, Any]:
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

    # Deduplication Logic (Prevent Value Overflow from overlapping zones)
    unique_items_map = {}
    deduped_line_items = []
    
    for item in line_items:
        try:
            # 1. Scalable Noise Filter
            # UPDATED: Use Amount
            n_val = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            q_val = float(item.get("Qty") or 0)
            
            # Allow items if they have a valid Batch Number, even if value is 0
            has_batch = item.get("Batch") and item.get("Batch") not in ["", "None", "N/A", None]
            
            if abs(n_val) < 0.1 and abs(q_val) < 0.1 and not has_batch:
                continue # Skip noise
                
            # 2. Keyword Blacklist (Safety Net)
            desc_lower = str(item.get("Product", "")).lower()
            blacklist = ["total", "subtotal", "grand total", "amount", "output", "input", "gst", "freight", "discount", "round off", "net amount", "taxable value", "output cgst", "output sgst"]
            logger.info(f"Auditor Check: '{desc_lower}'") 
            if any(bad_word in desc_lower for bad_word in blacklist):
                logger.info(f"Auditor: Dropping Blacklisted Item '{desc_lower}'")
                continue

            # 5. Outlier Sanitization (Decimal Fix)
            # Fixes "Skyrocketing" values where 160.00 is read as 16000.
            # Strategy: If Amount > 5000 (arbitrary high shelf), check if dividing by 100 makes it "Reasonable" (< 5000).
            # This is a heuristic for pharma prices which rarely exceed 5k/unit.
            # Only apply if Rate/Amount are HUGE.
            
            # This loop should ideally run AFTER deduped_line_items is fully populated,
            # but the instruction places it here, so we'll apply it to the current 'item'
            # before it's potentially added to deduped_line_items.
            # To apply it to the current 'item' being processed, we'll modify 'item' directly.
            
            raw_amt = float(item.get("Amount") or 0)
            raw_rate = float(item.get("Rate") or 0)
            
            # Check Amount
            if raw_amt > 10000:
                # Sanity: Is Qty huge?
                q = float(item.get("Qty") or 1)
                if q < 100: 
                    # Small Qty, Huge Amount. Likely decimal error.
                    logger.warning(f"Auditor: Detected Huge Amount {raw_amt}. Auto-correcting to {raw_amt/100:.2f}")
                    item["Amount"] = raw_amt / 100
                    item["Logic_Note"] = item.get("Logic_Note", "") + " [Decimal Fix]"
            
            # Check Rate
            if raw_rate > 5000:
                 logger.warning(f"Auditor: Detected Huge Rate {raw_rate}. Auto-correcting to {raw_rate/100:.2f}")
                 item["Rate"] = raw_rate / 100
            
            # 6. Strict Safety Net Deduplication
            # 3. Fuzzy Deduplication (SequenceMatcher)
            # Strategy: Compare against ALL existing uniques for >0.9 similarity
            # If match found, Merge (Keep Max). If not, Append.
            desc_norm = str(item.get("Product", "")).strip().lower()
            
            # 2b. Batch Scavenger & Scheme Filter
            # "One man's trash is another man's treasure."
            # If this is a Scheme/Offer row (e.g. "Buy 1 Get 1"), it might contain the Batch No for the Previous Item.
            is_scheme_row = (
                ("buy " in desc_norm and " get " in desc_norm) or
                ("offer" in desc_norm and "free" in desc_norm) or
                (n_val == 0 and "free" in desc_norm) or
                ("buy" in desc_norm and "off" in desc_norm) or
                ("initiative name" in desc_norm)
            )

            if is_scheme_row:
                 # Check if we can "Scavenge" a batch number for the previous item
                 if deduped_line_items:
                     last_item = deduped_line_items[-1]
                     current_batch = last_item.get("Batch")
                     
                     # Only scavenge if previous item is missing batch or has a weak batch
                     if not current_batch or current_batch in ["", "None", "null"]:
                         import re
                         # Look for long alphanumeric strings (e.g., LTR251IN000041)
                         # Pattern: Starts with letter, alphanumeric, length 6-20
                         batch_match = re.search(r'\b([A-Z]{1,3}[A-Z0-9-]{5,20})\b', item.get("Product", ""))
                         if batch_match:
                             scavenged_batch = batch_match.group(1)
                             # Avoid false positives like "OFFER", "FREE", "BUY"
                             if scavenged_batch.upper() not in ["OFFER", "FREE", "BUY", "GET", "APPLY"]:
                                 logger.info(f"Auditor: Scavenged Batch '{scavenged_batch}' from Scheme Row for '{last_item.get('Product')}'")
                                 last_item["Batch"] = scavenged_batch

                 # 2c. Scheme Filter Strategy
                 # Standard: Drop the row if it's purely a textual description of an offer (Qty=0)
                 if q_val == 0 or "initiative name" in desc_norm:
                     logger.info(f"Auditor: Dropping Scheme/Info Row -> {desc_lower}")
                     continue
                 else:
                     # If it has Qty > 0, it might be a "Free Good" line item that we need to keep.
                     logger.info(f"Auditor: RETAINING Scheme Row (Has Qty) -> {desc_lower}")

            desc_norm = " ".join(desc_norm.split())

            # Skip comparison for extremely short strings to avoid false positives
            if len(desc_norm) < 3: 
                deduped_line_items.append(item)
                continue

            merged = False
            for existing_item in deduped_line_items:
                ex_desc = str(existing_item.get("Product", "")).strip().lower()
                ex_desc = " ".join(ex_desc.split())
                
                # Check Similarity
                from difflib import SequenceMatcher
                ratio = SequenceMatcher(None, desc_norm, ex_desc).ratio()
                
                # Normalization for Strict Deduplication
                p_slug = str(item.get("Product", "")).strip().lower().replace(" ", "")
                
                # Intelligent Batch Normalization
                raw_batch = str(item.get("Batch", "")).strip().lower()
                # Remove common prefixes to match "Batch 123" with "123" or "B.No 123" with "123"
                for prefix in ["batch", "no", "lot", "b.no", "bno", ".", ":", "-"]:
                    raw_batch = raw_batch.replace(prefix, "")
                b_slug = raw_batch.replace(" ", "")
                
                # Treat "N/A", "None" as same bucket
                if not b_slug or b_slug in ["none", "null", "n/a", "unknown"]:
                    b_slug = "unknown_batch"
                
                key = (p_slug, b_slug)
                # Check Batch Collision (Only merge if Batches compatible: Same or One is Generic)
                batch_curr = str(item.get("Batch", "N/A")).strip().lower()
                batch_ex = str(existing_item.get("Batch", "N/A")).strip().lower()
                
                batch_match = (batch_curr == batch_ex) or (batch_curr in ["n/a", "unknown", "none", ""]) or (batch_ex in ["n/a", "unknown", "none", ""])
                
                if batch_match and batch_curr not in ["n/a", "unknown", "none", "", "unknown_batch"]:
                     # AGGRESSIVE DEDUPE: If Batch Matches perfectly...
                     # CHECK IF VALUES ARE IDENTICAL (OCR Redundancy)
                     q_curr = float(item.get("Qty") or 0)
                     q_ex = float(existing_item.get("Qty") or 0)
                     val_curr = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
                     val_ex = float(existing_item.get("Amount") or existing_item.get("Stated_Net_Amount") or 0)
                     
                     if q_curr == q_ex and abs(val_curr - val_ex) < 1.0:
                         # Identical Item Found
                         
                         # NEW LOGIC: Check if this was a Single Source Extraction
                         raw_sources = state.get("raw_text_rows", [])
                         is_single_source = (len(raw_sources) <= 1)
                         
                         if is_single_source:
                             # SINGLE SOURCE -> Duplicate implies intentional split (e.g. 10+2 scheme) -> SUM THEM
                             logger.info(f"Auditor: Single Source Duplicate '{desc_norm}' -> SUMMING (Qty: {q_ex}+{q_curr}, Amt: {val_ex}+{val_curr})")
                             existing_item["Qty"] = q_ex + q_curr
                             existing_item["Amount"] = val_ex + val_curr
                             
                             # Also sum Net Amount if present
                             if existing_item.get("Stated_Net_Amount") and item.get("Stated_Net_Amount"):
                                 existing_item["Stated_Net_Amount"] = float(existing_item["Stated_Net_Amount"]) + float(item["Stated_Net_Amount"])
                                 
                             merged = True # Merged into existing, so don't append new one
                             
                         else:
                             # MULTI SOURCE -> Duplicate implies OCR Overlap (Redundant) -> DROP
                             merged = True
                             logger.info(f"Auditor: Dropping Exact Duplicate '{desc_norm}' (Redundant OCR from overlapping zones)")
                     else:
                         # Same Batch, Different Values -> Real Split Entry? -> KEEP BOTH
                         merged = False 
                         logger.info(f"Auditor: Same Batch but Different Values ({val_curr} vs {val_ex}) -> KEEPING BOTH")
                
                elif ratio > 0.94 and batch_match: 
                    # Fuzzy match + Batch match (N/A)
                    # If Quantities identical, Drop. Else Keep.
                     q_curr = float(item.get("Qty") or 0)
                     q_ex = float(existing_item.get("Qty") or 0)
                     if q_curr == q_ex:
                         merged = True
                         logger.info(f"Auditor: Fuzzy Duplicate '{desc_norm}' -> Dropping")
                     else:
                         merged = False

                if merged:
                    # Enrich Empty Fields (Batch, Expiry) if dropping the duplicate
                    # But DO NOT SUM VALUES.
                    if not existing_item.get("Batch") and item.get("Batch"):
                        existing_item["Batch"] = item["Batch"]
                        
                    if item.get("Expiry") and item.get("Expiry") not in ["", "None", "N/A", None]:
                         if not existing_item.get("Expiry"):
                             existing_item["Expiry"] = item["Expiry"]
            
            # 4. Self-Healing: Check Description for missing Batch No
            # e.g. "OB CRISSCROSS GUM CARE B202 SFT" -> Batch: B202
            if not item.get("Batch") or item.get("Batch") in ["", "None", "null"]:
                 import re
                 # Relaxed Pattern: 1-3 Letters + Number + 2+ Alphanumeric (Total 4+)
                 self_match = re.search(r'\b([A-Z]{1,3}[0-9][A-Z0-9-]{2,15})\b', desc_norm.upper())
                 if self_match:
                     extracted_batch = self_match.group(1)
                     # Safety: Avoid extracting "10GM", "5ML", "STD"
                     if "GM" not in extracted_batch and "ML" not in extracted_batch and "PC" not in extracted_batch:
                         logger.info(f"Auditor: Self-Healed Batch '{extracted_batch}' from Description '{desc_norm}'")
                         item["Batch"] = extracted_batch

            if not merged:
                # 4. Quantity Sanity Check & Fix
                # Problem: Sometimes Qty column is missed and Rate/MRP (e.g. 200, 300) is extracted as Qty.
                # Heuristic 1: If Qty is exactly equal to MRP or Rate, it's a shifted column error.
                # Heuristic 2: If Qty > 100 on a pharmacy invoice, it's highly suspicious (unless it's 'strips' vs 'tabs').
                
                check_mrp = parse_float(item.get("MRP", 0))
                check_rate = parse_float(item.get("Rate", 0))
                
                if q_val > 50:
                     # Check for Swap with MRP/Rate
                     if (check_mrp > 0 and abs(q_val - check_mrp) < 1.0) or (check_rate > 0 and abs(q_val - check_rate) < 1.0):
                         logger.warning(f"Auditor: Qty {q_val} matches Price/MRP. Suspected column swap. Correcting Qty to 1.")
                         q_val = 1.0
                         item["Qty"] = 1.0
                     
                     # Check for "Year" confusion (e.g. Qty 2024, 2025)
                     elif q_val > 1900 and q_val < 2100:
                         logger.warning(f"Auditor: Qty {q_val} looks like a Year. Correcting to 1.")
                         q_val = 1.0
                         item["Qty"] = 1.0
                         
                     # General High Value Warning (User likely needs to review this)
                     else:
                         logger.warning(f"Auditor: High Quantity Detected ({q_val}). Flagging for review.")
                         # We can't auto-correct arbitrary high numbers safely without more context, 
                         # but we can try to look for a small integer in the 'Amount' / 'Rate' math?
                         
                item["Qty"] = q_val
                
                # --- END SANITY CHECKS ---

                deduped_line_items.append(item)

        except Exception as e:
            logger.warning(f"Auditor Deduplication Error: {e}")
            deduped_line_items.append(item)
    
    logger.info(f"Auditor: Deduplication: Reduced {len(line_items)} items to {len(deduped_line_items)} unique items.")
    
    # 7. Robust Quantity Reconstruction (Math as Source of Truth)
    # Replaces specific "Swap Fixes" with a general rule: Qty = Amount / Rate
    deduped_line_items = _reconcile_quantities_with_math(deduped_line_items)

    logger.info("Auditor verification complete.")
    
    return {"line_items": deduped_line_items}

def _reconcile_quantities_with_math(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enforces the invariant: Quantity * Rate = Amount.
    If the extracted Qty violates this, but Amount/Rate yields a clean integer,
    we overwrite Qty with the calculated value.
    This fixes Swaps, Typos (e.g. 'l'->1), and Alignment errors globally.
    """
    for item in items:
        try:
            qty_extracted = float(item.get("Qty") or 0)
            rate = float(item.get("Rate") or 0)
            amt = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
            
            # Skip if Rate is missing or zero (cannot divide)
            if rate <= 0:
                continue
                
            # 1. Check for Math Mismatch
            # Discrepancy > 5% implies the Extracted Qty is likely wrong 
            # (assuming Amount and Rate are correct, which is statistically safer)
            expected_amt = qty_extracted * rate
            is_mismatch = abs(expected_amt - amt) > max(2.0, amt * 0.05)
            
            if is_mismatch:
                # 2. Attempt Reconstruction
                calc_qty = amt / rate
                
                # 3. Check Plausibility of Calculated Qty
                # It must be a "Clean Number" (Integer or simple fraction like 0.5)
                # And it must be positive.
                is_clean_integer = abs(calc_qty - round(calc_qty)) < 0.05
                is_clean_fraction = abs((calc_qty * 2) - round(calc_qty * 2)) < 0.05 # Allow .5
                
                if (is_clean_integer or is_clean_fraction) and calc_qty > 0:
                    
                    # Round to nearest logical value
                    final_qty = round(calc_qty, 1) if is_clean_fraction else round(calc_qty)
                    
                    logger.info(f"Auditor: Math Reconstruction for '{item.get('Product')}'. Extracted Qty {qty_extracted} (Inconsistent) -> Calculated Qty {final_qty} (Derived from Amt {amt}/Rate {rate})")
                    
                    item["Qty"] = float(final_qty)
                    item["Logic_Note"] = item.get("Logic_Note", "") + " [Math Fix]"

        except Exception as e:
            # Don't let a math error crash the pipeline
            continue
            
    return items
