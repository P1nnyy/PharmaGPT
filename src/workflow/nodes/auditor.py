import google.generativeai as genai
import json
import os
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger

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

                 # disable_scheme_filter: USER REQUEST: Keep all rows for raw extract. 
                 # logger.info(f"Auditor: Removing Scheme Row -> {desc_lower}")
                 # continue
                 logger.info(f"Auditor: RETAINING Scheme Row -> {desc_lower}")

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
                
                # Check Batch Collision (Only merge if Batches compatible: Same or One is Generic)
                batch_curr = str(item.get("Batch", "N/A")).strip().lower()
                batch_ex = str(existing_item.get("Batch", "N/A")).strip().lower()
                
                batch_match = (batch_curr == batch_ex) or (batch_curr in ["n/a", "unknown", "none", ""]) or (batch_ex in ["n/a", "unknown", "none", ""])
                
                if ratio > 0.94 and batch_match: # 94% threshold: Matches "6s"/"65" but separates "5gm"/"10gm"
                    merged = True
                    # Merge Logic: Keep MAX Amount
                    val_curr = float(item.get("Amount") or item.get("Stated_Net_Amount") or 0)
                    val_ex = float(existing_item.get("Amount") or existing_item.get("Stated_Net_Amount") or 0)
                    
                    if val_curr > val_ex:
                        logger.info(f"Auditor: Fuzzy Merge '{desc_norm}' > '{ex_desc}' (Keeping {val_curr})")
                        
                        # PRESERVE METADATA: If 'existing_item' has Batch/Exp but 'item' (Main) doesn't,
                        # don't let update() wipe it out!
                        saved_batch = existing_item.get("Batch")
                        saved_exp = existing_item.get("Expiry")
                        
                        # Update existing item in place (Python list contains ref to dict)
                        existing_item.update(item) 
                        
                        if not existing_item.get("Batch") and saved_batch not in ["", "None", "N/A", None]:
                            existing_item["Batch"] = saved_batch
                            
                        if not existing_item.get("Expiry") and saved_exp not in ["", "None", "N/A", None]:
                            existing_item["Expiry"] = saved_exp
                    else:
                        logger.info(f"Auditor: Fuzzy Dropped '{desc_norm}' (Keeping {val_ex})")
                        # SMART MERGE: Even if we drop the 'item' (because it has no price),
                        # we should steal its Batch/Exp if the 'existing_item' lacks them.
                        if item.get("Batch") and item.get("Batch") not in ["", "None", "N/A", None]:
                             if not existing_item.get("Batch"):
                                 existing_item["Batch"] = item["Batch"]
                                 logger.info(f"Auditor: enriched '{desc_norm}' with Batch {item['Batch']}")
                        
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
                deduped_line_items.append(item)

        except Exception as e:
            logger.warning(f"Auditor Deduplication Error: {e}")
            deduped_line_items.append(item)
    
    logger.info(f"Auditor: Deduplication: Reduced {len(line_items)} items to {len(deduped_line_items)} unique items.")
    logger.info("Auditor verification complete.")
    
    return {"line_items": deduped_line_items}
