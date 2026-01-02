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
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = """
        TASK: EXTRACT SUPPLIER / SELLER DETAILED METADATA.
        
        CRITICAL INSTRUCTION: SCAN THE ENTIRE HEADER AREA, INCLUDING CORNERS.
        - **Top-Left Corner often contains DL No. or Phone Numbers.**
        - **Top-Right Corner often contains Date/Invoice No (ignore) but sometimes Phones.**
        - Look distinctly at the text *above* and *around* the Supplier Name.
        
        Focus ONLY on the Seller/Supplier section.
        Ignore the Buyer/Bill-To section.
        Ignore Line Items.
        
        TARGET FIELDS:
        1. **Supplier_Name**: The name of the shop/distributor.
        2. **Address**: Full physical address.
        4. **GSTIN**: GST Number (15 Digits/Chars). 
           - **CRITICAL**: Sometimes labeled as "CST", "VST", "VAT", "TIN", or just "No".
           - Look for patterns like `03AAJFR...` (State Code + PAN + Entity Code).
           - If you see a 15-char code starting with 2 digits, IT IS LIKELY THE GSTIN.
           - DO NOT confusing it with PAN (10 chars).
        5. **DL_No**: Drug License Numbers.
           - Look for "D.L.No", "20B", "21B", "Lic No", "Drug Lic", "L.No" near the Supplier Name.
           - Capture BOTH 20B and 21B numbers if present.
           - **CRITICAL**: Do NOT capture DL Numbers that belong to the "Buyer", "Bill To", or "Party" section.
        5. **Phone_Number**: Contact numbers. Look near Supplier Name or Top/Bottom margins.
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
        
        - If a field is missing, return None. 
        - DO NOT hallucinate.
        - Output pure JSON only.
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
                
                if not data:
                    is_valid = False
                    errors.append("Output was not valid JSON.")
                else:
                    raw_gst = data.get("GSTIN")
                    if raw_gst:
                         g = str(raw_gst).replace(" ", "").replace("-", "").upper()
                    else:
                         g = ""

                    if not g:
                        # Fallback: Check if PAN looks like a GSTIN
                        raw_pan = data.get("PAN")
                        if raw_pan and len(str(raw_pan)) == 15:
                             g = str(raw_pan).strip().upper()
                             data["GSTIN"] = g
                             data["PAN"] = g[2:12] # Extract PAN from GSTIN
                             logger.info(f"SupplierExtractor: Promoted PAN {g} to GSTIN.")
                        else:
                            is_valid = False
                            errors.append("GSTIN is Missing.")
                    
                    if g:
                        if len(g) != 15:
                            if len(g) < 10 or len(g) > 18:
                                is_valid = False
                                errors.append(f"GSTIN '{g}' is invalid length ({len(g)}).")
                            
                    if not data.get("Supplier_Name"):
                         is_valid = False
                         errors.append("Supplier Name is Missing.")

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
