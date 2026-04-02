from src.services.ai_client import manager
import os
import json
import logging
from typing import Dict, Any, List
from src.workflow.state import InvoiceState as InvoiceStateDict
from src.utils.logging_config import get_logger
from src.utils.ai_retry import ai_retry

# Setup Logging
logger = get_logger("surveyor")

from langfuse import observe

@ai_retry
@observe(name="surveyor_layout_analysis")
async def survey_document(state: InvoiceStateDict) -> Dict[str, Any]:
    """
    Layout Discovery Node.
    Analyzes the document image to identify distinct zones (tables, footers).
    Returns an update to the state with 'extraction_plan'.
    """
    image_path = state.get("image_path")
    if not image_path or not os.path.exists(image_path):
        logger.error(f"Image not found at {image_path}")
        return {"extraction_plan": [], "error_logs": [f"Image not found: {image_path}"]}

    try:
        # Validate Image
        if os.path.getsize(image_path) == 0:
            logger.error(f"Image is empty: {image_path}")
            return {"extraction_plan": [], "error_logs": ["Image file is empty"]}

        # Preprocess Image before Surveying (Rotation/Binarization)
        from src.utils.image_processing import preprocess_image_for_ocr
        import tempfile
        
        logger.info("Surveyor: Preprocessing image before layout analysis...")
        processed_bytes = preprocess_image_for_ocr(image_path)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(processed_bytes)
            tmp_image_path = tmp_file.name
            
        # Upload file with Retries
        sample_file = None
        upload_retries = 3
        for attempt in range(upload_retries):
            try:
                sample_file = await manager.upload_file_async(file_path=tmp_image_path)
                logger.info(f"File uploaded successfully: {sample_file.name}")
                break
            except Exception as e:
                logger.warning(f"Upload Attempt {attempt+1} failed: {e}")
                import asyncio
                await asyncio.sleep(2) # Wait before retry
                if attempt == upload_retries - 1:
                     return {"extraction_plan": [], "error_logs": [f"Surveyor Upload Failed: {str(e)}"]}
        
        # Cleanup Tmp File
        try:
            os.unlink(tmp_image_path)
        except:
            pass
        
        prompt = """
        Analyze this invoice and identify distinct layout zones.
        
        CRITICAL GOAL: Distinguish the "Main Product Line Item Table" from "Tax/HSN Summaries".
        
        42. Primary Table (Product List):
           - **MUST CONTAIN** a column for 'Description', 'Item Name', 'Product', or 'Particulars'.
           - It usually spans the middle of the document.
           - Label this zone_type: "primary_table".
           - **DISTINCTION**: If a table has "HSN" and "Tax" columns but **LACKS** a "Description/Item Name" column, it is a TAX SUMMARY. Ignore it.
           - Use zone_id: "table_1".
 
        2. Secondary Tables (IGNORE THESE AS PRIMARY):
           - **Tax Summary / HSN Summary**: Often at the bottom, contains 'Taxable Amt', 'CGST', 'SGST', 'Total Tax'. **DO NOT** claim this as the primary table.
           - **Schemes / Free Goods**: Small detached tables.
 
        3. Header: Top section with Supplier Name, Invoice Date, Invoice No.
        4. Footer: Bottom section with Grand Total, Net Payable, Bank Details.
        
        Output JSON Schema (Normalized Coordinates 0-1000): 
        [
            {
                "zone_id": "header_1",
                "type": "header",
                "ymin": 0, "xmin": 0, "ymax": 200, "xmax": 1000,
                "description": "Top section with supplier details"
            },
            {
                "zone_id": "table_1", 
                "type": "primary_table", 
                "ymin": 200, "xmin": 0, "ymax": 850, "xmax": 1000,
                "description": "Main product grid"
            },
            {
                "zone_id": "footer_1",
                "type": "footer",
                "ymin": 850, "xmin": 0, "ymax": 1000, "xmax": 1000,
                "description": "Footer area with Grand Total"
            }
        ]
        """

        # Generate content with the new SDK via manager (throttled)
        response = await manager.generate_content_async(
            model='gemini-2.0-flash',
            contents=[prompt, sample_file]
        )
        response_text = response.text
        
        # Clean Code Blocks
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        extraction_plan = json.loads(clean_json)
        
        logger.info(f"Surveyor Plan: {len(extraction_plan)} zones identified.")
        return {"extraction_plan": extraction_plan}

    except Exception as e:
        logger.error(f"Surveyor failed after retries: {e}")
        return {"extraction_plan": [], "error_logs": [f"Surveyor Error: {str(e)}"]}
