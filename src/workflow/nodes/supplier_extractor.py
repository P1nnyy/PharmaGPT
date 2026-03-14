import google.generativeai as genai
import json
import os
from typing import Dict, Any
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.utils.image_processing import preprocess_image_for_ocr
import tempfile

logger = get_logger(__name__)

async def extract_supplier_details(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Specialized Node to extract Supplier details (GST, DL, Phone, Address).
    Runs in parallel to the main worker.
    """
    image_path = state.get("image_path")
    if not image_path:
        return {"error_logs": ["SupplierExtractor: Missing image path."]}
        
    logger.info("SupplierExtractor: Starting specialized extraction...")
    
    try:
        # We can reuse the same preprocessing or use raw image. 
        # Supplier details are usually clear enough on the header.
        # Let's use the provided image path directly to save time, 
        # as Gemini handles images well.
        
        sample_file = genai.upload_file(path=image_path, display_name="Supplier Extraction")
        # Retry 2.0 Flash with the NEW Prompt (It should work now)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = """
        TASK: EXTRACT SUPPLIER / SELLER DETAILS FROM A PHARMA DISTRIBUTOR TAX INVOICE.
        
        ═══════════════════════════════════════════════════════════
        MOST CRITICAL RULE — READ BEFORE ANYTHING ELSE:
        ═══════════════════════════════════════════════════════════
        A pharmaceutical distributor invoice has TWO parties:
        1. **SELLER / SUPPLIER** (the company generating the invoice):
           - Found under labels like: "Registered Name", "Firm Name", "Company Name",
             "From:", "Sold By:", "Distributor:", "Retailer Name" at the top.
           - They have a GSTIN, DL No, and PAN.
           - This is WHO YOU WANT.
        
        2. **BUYER / CUSTOMER** (the shop receiving the goods):
           - Found under labels like: **"Customer Name"**, **"Bill To"**, **"Party Name"**,
             **"Customer:"**, **"Consignee"**, "Purchaser".
           - **NEVER extract the Buyer as the Supplier.**
           - **If you see the word "Customer" before a name, that name is the BUYER. IGNORE IT.**
        
        ═══════════════════════════════════════════════════════════
        STRATEGY:
        ═══════════════════════════════════════════════════════════
        Step 1: Find the block labeled "Customer Name", "Bill To", or "Party Name". 
                EXCLUDE that entity completely from your result.
        Step 2: Look for the entity with GSTIN/DL No. That is almost always the Seller.
        Step 3: The Seller name is often in the TOP-LEFT header or labeled "Registered Name".
        Step 4: Use the GSTIN to confirm — the Seller is always the one with a GSTIN on the invoice.
        
        ═══════════════════════════════════════════════════════════
        TARGET FIELDS (for the SELLER only):
        ═══════════════════════════════════════════════════════════
        1. **Supplier_Name**: Name of the seller/distributor.
           - This is NEVER the entity next to "Customer Name:", "Bill To:", or "Consignee:".
           - Usually near the top, near the GSTIN, DL No.
        2. **Address**: Full physical address of the seller.
        3. **GSTIN**: 15-character GST Number.
        4. **DL_No**: Drug License Numbers (keywords: D.L., Lic No, 20B, 21B).
        5. **Phone_Number**: Contact number.
        6. **Email**: Email address.
        7. **PAN**: PAN Number.
        
        Return JSON structure:
        {
            "Supplier_Name": "string",
            "Address": "string",
            "GSTIN": "string",
            "DL_No": "string",
            "Phone_Number": "string",
            "Email": "string",
            "PAN": "string"
        }
        
        - Return null for missing fields.
        - DO NOT hallucinate.
        - Output PURE JSON only.
        """
        
        # RETRY LOGIC (Max 3 Attempts with Feedback)
        max_retries = 3
        data = {}
        feedback_instruction = ""
        
        for attempt in range(max_retries):
            logger.info(f"SupplierExtractor: Attempt {attempt+1}/{max_retries}")
            
            # Append feedback if this is a retry
            current_prompt = prompt + feedback_instruction
            
            try:
                response = await model.generate_content_async(
                    [current_prompt, sample_file],
                    generation_config={"response_mime_type": "application/json"}
                )
                text = response.text.strip()
                
                # Parse JSON
                import re
                clean_text = text.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(clean_text)
                except:
                    json_match = re.search(r"\{.*\}", text, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                        except Exception as e:
                           pass
                           
                # Handle List output (common with Gemini JSON mode)
                if isinstance(data, list):
                    data = data[0] if data else {}
                           
                # --- VERIFICATION SYSTEM ---
                # Check for Critical Fields & Format
                is_valid = True
                errors = []
                
                # LOG RAW DATA for Debugging
                logger.info(f"SupplierExtractor: Raw Data: {data}")

                if not data:
                    is_valid = False
                    errors.append("Output was not valid JSON.")
                else:
                    raw_gst = data.get("GSTIN")
                    if raw_gst:
                         g = str(raw_gst).replace(" ", "").replace("-", "").upper()
                         # Validate Length loosely
                         if len(g) < 10 or len(g) > 18:
                             logger.warning(f"SupplierExtractor: GSTIN '{g}' seems invalid length ({len(g)}). Keeping it anyway.")
                    
                    if not data.get("Supplier_Name"):
                         is_valid = False
                         errors.append("Supplier Name is Missing.")
                    
                    # RELAXED VALIDATION:
                    # If we have a Name, we accept the result.
                    # We do NOT fail just because GSTIN is missing.
                    if is_valid:
                        logger.info("SupplierExtractor: Validation Passed (Relaxed Mode).")

                if is_valid:
                    # Success!
                    raw_gst = data.get("GSTIN")
                    if raw_gst:
                        data["GSTIN"] = str(raw_gst).replace(" ", "").replace("-", "").upper()
                    break
                else:
                    logger.warning(f"SupplierExtractor: Attempt {attempt+1} Failed Verification: {errors}")
                    feedback_instruction = f"\n\nPREVIOUS ATTEMPT FAILED. ISSUES: {', '.join(errors)}. PLEASE EXTRACT CAREFULLY."
                    data = {} # Clear partial data
                    
            except Exception as e:
                logger.error(f"SupplierExtractor: Attempt {attempt+1} Exception: {e}")
            
        if not data:
            return {"error_logs": ["SupplierExtractor: Failed to extract valid data after retries."]}
             
        logger.info(f"SupplierExtractor: Extracted {data.get('Supplier_Name')} with GSTIN {data.get('GSTIN')}")
        
        return {
            "supplier_details": data
        }

    except Exception as e:
        logger.error(f"SupplierExtractor Error: {e}")
        return {"error_logs": [f"SupplierExtractor Failed: {str(e)}"]}
