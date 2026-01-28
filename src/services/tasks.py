import os
from src.utils.logging_config import get_logger
from src.services.database import get_db_driver
from src.workflow.graph import run_extraction_pipeline
from src.domain.schemas import InvoiceExtraction
from src.domain.normalization import normalize_line_item, parse_float, reconcile_financials
from src.domain.persistence import update_invoice_status

logger = get_logger(__name__)

async def process_invoice_background(invoice_id, local_path, public_url, user_email, original_filename):
    """
    Background Task: Runs extraction and updates DB status.
    """
    driver = get_db_driver()
    
    try:
        print(f"Starting Background Processing for {invoice_id}...")
        
        # Run Extraction
        extracted_data = await run_extraction_pipeline(local_path, user_email, public_url=public_url)
        
        if extracted_data is None:
             raise ValueError("Extraction yielded None")
             
        extracted_data["image_path"] = public_url
        # print(f"DEBUG: Extracted Data Keys: {list(extracted_data.keys())}")
        
        # Normalize
        invoice_obj = InvoiceExtraction(**extracted_data)
        normalized_items = []
        for raw_item in invoice_obj.Line_Items:
            # Handle Pydantic v1/v2 compatibility
            raw_dict = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            norm_item = normalize_line_item(raw_dict, invoice_obj.Supplier_Name)
            normalized_items.append(norm_item)
            
        # Reconcile
        grand_total = parse_float(extracted_data.get("Stated_Grand_Total") or extracted_data.get("Invoice_Amount", 0.0))
        normalized_items = reconcile_financials(normalized_items, extracted_data, grand_total)
        
        # Validation checks
        validation_flags = []
        calculated_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
        if grand_total:
             if abs(calculated_total - grand_total) > 5.0:
                 validation_flags.append(f"Mismatch: Calc {calculated_total:.2f} != Stated {grand_total:.2f}")

        # Construct Final Result State
        result_state = {
            "status": "review_needed",
            "invoice_data": extracted_data,
            "normalized_items": normalized_items,
            "validation_flags": validation_flags,
            "filename": original_filename
        }
        
        # Update Neo4j Status -> DRAFT
        update_invoice_status(driver, invoice_id, "DRAFT", result_state)
        print(f"Background Processing Complete for {invoice_id} -> DRAFT")
        
    except Exception as e:
        logger.error(f"Background Task Failed for {invoice_id}: {e}")
        import traceback
        traceback.print_exc()
        # Update Neo4j Status -> ERROR
        update_invoice_status(driver, invoice_id, "ERROR", error=str(e))
    finally:
        # cleanup
        if os.path.exists(local_path):
            os.remove(local_path)

async def enrich_invoice_items_background(normalized_items: list, user_email: str):
    """
    Background Task: Enriches all items in a saved invoice with manufacturer/salt details.
    """
    from src.services.enrichment_agent import EnrichmentAgent
    
    logger.info(f"Starting Bulk Enrichment for {len(normalized_items)} items...")
    driver = get_db_driver()
    agent = EnrichmentAgent()
    
    # Iterate and Enrich
    for item in normalized_items:
        product_name = item.get("Standard_Item_Name")
        if not product_name:
            continue
            
        try:
            # Check if already enriched in DB? 
            # Optimization: If db already has manufacturer, skip? 
            # For now, let's trust the "latest" source or maybe skip if valid.
            # But user might want to fill gaps. Let's check first.
            
            check_query = """
            MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
            RETURN gp.manufacturer as m, gp.salt_composition as s
            """
            
            needs_enrichment = True
            with driver.session() as session:
                rec = session.run(check_query, user_email=user_email, name=product_name).single()
                if rec and rec["m"] and rec["m"] != "Unknown" and rec["s"]:
                     needs_enrichment = False
            
            if not needs_enrichment:
                logger.info(f"Skipping enrichment for {product_name} (Already present)")
                continue

            logger.info(f"Enriching Invoice Item: {product_name}")
            local_pack_size = item.get("Pack_Size_Description")
            result = agent.enrich_product(product_name, local_pack_size=local_pack_size)
            
            if result.get("error"):
                logger.warning(f"Enrichment Error for {product_name}: {result['error']}")
                continue
                
            # Update DB
            update_query = """
            MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
            SET gp.manufacturer = $manufacturer,
                gp.salt_composition = $salt,
                gp.category = $category,
                gp.is_verified = true,
                gp.updated_at = timestamp()
            """
            
            with driver.session() as session:
                session.run(update_query, 
                            user_email=user_email,
                            name=product_name,
                            manufacturer=result.get("manufacturer"),
                            salt=result.get("salt_composition"),
                            category=result.get("category"))
                            
            logger.info(f"Enriched {product_name}: {result.get('manufacturer')}")
            
        except Exception as e:
            logger.error(f"Failed to enrich item {product_name}: {e}")

