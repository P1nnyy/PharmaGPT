import os
import asyncio
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
    import asyncio
    print(f"DEBUG LOOP process_invoice_background [{invoice_id}]: {id(asyncio.get_running_loop())}")
    from src.services.task_manager import manager as task_manager
    # Register current task for cancellation tracking
    current_task = asyncio.current_task()
    task_manager.register(user_email, invoice_id, current_task)
    
    driver = get_db_driver()
    
    try:
        print(f"Starting Background Processing for {invoice_id}...")
        
        # 1. R2 Upload (Move from API to background to avoid timeout)
        if not public_url:
            from src.services.storage import upload_to_r2
            
            logger.info(f"Uploading {invoice_id} to R2 in background...")
            file_ext = f".{original_filename.split('.')[-1]}" if '.' in original_filename else ".png"
            filename = f"{invoice_id}{file_ext}"
            
            try:
                with open(local_path, "rb") as f_read:
                    # Run blocking S3 upload in a separate thread
                    public_url = await asyncio.to_thread(upload_to_r2, f_read, filename)
                
                if public_url:
                    logger.info(f"R2 Upload Complete for {invoice_id}: {public_url}")
                    # Update Neo4j node with the URL immediately so UI can show it
                    # result_state=None for now, just updating the metadata
                    update_invoice_status(driver, invoice_id, "PROCESSING", result_state={"image_path": public_url})
                else:
                    logger.warning(f"R2 Upload failed for {invoice_id}. Preview might be missing.")
            except Exception as e:
                 logger.error(f"Failed to upload to R2 in background: {e}")

        # 2. Run Extraction
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
        grand_total = extracted_data.get("Stated_Grand_Total") or extracted_data.get("grand_total")
        recon_result = reconcile_financials(normalized_items, extracted_data, grand_total)
        normalized_items = recon_result.get("line_items", [])
        calc_stats = recon_result.get("calculated_stats", {})
        
        # HEAL: Update extracted_data with Reconciled Values for the Frontend UI
        # This ensures the summary box shows the same numbers as our internal math
        extracted_data["sub_total"] = calc_stats.get("sub_total", 0.0)
        extracted_data["taxable_value"] = calc_stats.get("taxable_value", 0.0)
        extracted_data["total_sgst"] = calc_stats.get("total_sgst", 0.0)
        extracted_data["total_cgst"] = calc_stats.get("total_cgst", 0.0)
        extracted_data["round_off"] = calc_stats.get("round_off", 0.0)
        # Match UI to Reconciled Reality (Override Stated Total if it was rounded)
        extracted_data["grand_total"] = calc_stats.get("grand_total", 0.0)
        extracted_data["Stated_Grand_Total"] = calc_stats.get("grand_total", 0.0)
        # Compatibility with CamelCase fields in schema
        extracted_data["SGST_Amount"] = calc_stats.get("total_sgst", 0.0)
        extracted_data["CGST_Amount"] = calc_stats.get("total_cgst", 0.0)
        extracted_data["Round_Off"] = calc_stats.get("round_off", 0.0)
        
        # Validation checks
        validation_flags = []
        calculated_total = calc_stats.get("grand_total") or 0.0
        if grand_total and abs(calculated_total - grand_total) > 1.0:
             validation_flags.append(f"Calculation Audit: Reconciled Total ₹{calculated_total:.2f} differs from Stated ₹{grand_total:.2f}. Please verify.")

        # Construct Final Result State
        result_state = {
            "status": "review_needed",
            "invoice_data": extracted_data,
            "normalized_items": normalized_items,
            "validation_flags": validation_flags,
            "filename": original_filename,
            "image_path": public_url
        }
        
        # Update Neo4j Status -> DRAFT
        update_invoice_status(driver, invoice_id, "DRAFT", result_state)
        print(f"Background Processing Complete for {invoice_id} -> DRAFT")
        
    except asyncio.CancelledError:
        logger.info(f"Background task for {invoice_id} was explicitly cancelled.")
        # No need to update DB as the route usually deletes the node anyway, 
        # but if it doesn't, we can set it to a terminal state.
        raise # Re-raise to ensure the task actually stops
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
                rec = session.execute_read(lambda tx: tx.run(check_query, user_email=user_email, name=product_name).single())
                if rec and rec["m"] and rec["m"] != "Unknown" and rec["s"]:
                     needs_enrichment = False
            
            if not needs_enrichment:
                logger.info(f"Skipping enrichment for {product_name} (Already present)")
                continue

            logger.info(f"Enriching Invoice Item: {product_name}")
            local_pack_size = item.get("Pack_Size_Description")
            result = await agent.enrich_product(product_name, local_pack_size=local_pack_size)
            
            if result.get("error"):
                logger.warning(f"Enrichment Error for {product_name}: {result['error']}")
                continue
                
            # Check if valid data was returned
            if not result.get("manufacturer") and not result.get("salt_composition"):
                logger.warning(f"Enrichment returned empty data for {product_name}. Skipping save.")
                continue

            # Update DB
            update_query = """
            MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
            SET gp.manufacturer = $manufacturer,
                gp.salt_composition = $salt,
                gp.category = $category,
                gp.is_enriched = true,
                gp.updated_at = timestamp()
            """
            
            with driver.session() as session:
                session.execute_write(lambda tx: tx.run(update_query, 
                            user_email=user_email,
                            name=product_name,
                            manufacturer=result.get("manufacturer"),
                            salt=result.get("salt_composition"),
                            category=result.get("category")))
                            
            logger.info(f"Enriched {product_name}: {result.get('manufacturer')}")

            # ---------------------------------------------------------
            # Fix: Update Packaging Unit based on Enriched Category
            # ---------------------------------------------------------
            from src.domain.normalization.text import structure_packaging_hierarchy
            
            enrichment_category = result.get('category')
            pack_info = structure_packaging_hierarchy(local_pack_size, enrichment_category=enrichment_category)
            
            if pack_info and pack_info.get("base_unit"):
                new_base_unit = pack_info.get("base_unit")
                logger.info(f"Correcting Base Unit for {product_name} -> {new_base_unit} (Cat: {enrichment_category})")
                
                unit_update_query = """
                MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
                SET gp.base_unit = $base_unit,
                    gp.unit_name = $base_unit
                """
                with driver.session() as session:
                    session.execute_write(lambda tx: tx.run(unit_update_query, 
                                user_email=user_email, 
                                name=product_name, 
                                base_unit=new_base_unit))

        except Exception as e:
            logger.error(f"Failed to enrich item {product_name}: {e}")

