import os
import asyncio
import json
from src.utils.logging_config import get_logger
from src.services.database import get_db_driver
from src.workflow.graph import run_extraction_pipeline
from src.domain.schemas import InvoiceExtraction
from src.domain.normalization import normalize_line_item, parse_float, reconcile_financials
from src.domain.persistence import update_invoice_status

logger = get_logger(__name__)

async def process_invoice_background(invoice_id, local_path, public_url, user_email, tenant_id, original_filename):
    """
    Background Task: Runs extraction and updates DB status.
    """
    import asyncio
    print(f"DEBUG LOOP process_invoice_background [{invoice_id}]: {id(asyncio.get_running_loop())}")
    from src.services.task_manager import manager as task_manager
    # Register current task for cancellation tracking
    from src.utils.image_processing import enforce_portrait_rotation
    driver = get_db_driver()
    
    try:
        print(f"Starting Background Processing for {invoice_id}...")
        
        # --- Tenant ID Fallback ---
        if not tenant_id or tenant_id == "anonymous":
            with driver.session() as session:
                shop_res = session.run("MATCH (u:User {email: $email})-[:OWNS_SHOP|WORKS_AT]->(s:Shop) RETURN s.id as id LIMIT 1", email=user_email).single()
                if shop_res:
                    tenant_id = shop_res["id"]
                    logger.info(f"Fallback Tenant ID found for {user_email}: {tenant_id}")
                else:
                    logger.warning(f"No shop found for {user_email}. Using 'anonymous' as fallback.")
                    tenant_id = "anonymous"
        
        # 0. Enforce Portrait Orientation (User Request)
        # This overwrites local_path with a corrected portrait image before upload to R2
        enforce_portrait_rotation(local_path)
        
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
                    update_invoice_status(driver, invoice_id, "PROCESSING", tenant_id, result_state={"image_path": public_url})
                else:
                    logger.warning(f"R2 Upload failed for {invoice_id}. Preview might be missing.")
            except Exception as e:
                 logger.error(f"Failed to upload to R2 in background: {e}")

        # 2. Run Extraction (The Single Source of Truth)
        from src.domain.persistence import update_invoice_status
        
        async def on_graph_update(node, message):
            logger.info(f"AG-UI Update [{invoice_id}]: {message}")
            # Update Neo4j message so SSE picks it up
            update_invoice_status(driver, invoice_id, "PROCESSING", tenant_id, status_message=message)

        extracted_data = await run_extraction_pipeline(local_path, user_email, public_url=public_url, on_update=on_graph_update)
        
        if extracted_data is None:
             raise ValueError("Extraction yielded None")
             
        extracted_data["image_path"] = public_url
        trace_id = extracted_data.get("trace_id", "unknown")

        # 3. Local Debug Logging (User Request)
        try:
             dbg_path = f"/tmp/pharma_dbg_{trace_id}.json"
             with open(dbg_path, "w") as f:
                 json.dump(extracted_data, f, indent=4)
             logger.info(f"Local Debug State saved to {dbg_path}")
        except Exception as e:
             logger.error(f"Failed to save local debug state: {e}")
        
        # 4. Final state mapping
        # We NO LONGER re-run reconcile_financials here. We trust the pipeline.
        # But we ensure extracted_data has everything the UI needs.
        calculated_total = parse_float(extracted_data.get("grand_total") or 0.0)
        stated_total = parse_float(extracted_data.get("Stated_Grand_Total") or 0.0)

        # Validation checks
        validation_flags = []
        if stated_total > 0 and abs(calculated_total - stated_total) > 2.0:
             validation_flags.append(f"Calculation Audit: Reconciled Total ₹{calculated_total:.2f} differs from Stated ₹{stated_total:.2f}. Please verify.")

        # Construct Final Result State
        supplier_name = extracted_data.get("Supplier_Name", "")
        # Run normalization to map internal schema (Product, Batch, Qty) to UI schema (Standard_Item_Name, Batch_No, Standard_Quantity)
        line_items_results = extracted_data.get("Line_Items", [])
        normalized_items = []
        for item in line_items_results:
             normalized = normalize_line_item(item, supplier_name)
             normalized_items.append(normalized)
        
        if normalized_items:
             logger.info(f"DEBUG: First Normalized Item Keys: {list(normalized_items[0].keys())}")
             logger.info(f"DEBUG: First Item Standard Name: {normalized_items[0].get('Standard_Item_Name')}")

        result_state = {
            "status": "review_needed",
            "invoice_data": extracted_data,
            "normalized_items": normalized_items,
            "validation_flags": validation_flags,
            "filename": original_filename,
            "image_path": public_url,
            "supplier_name": extracted_data.get("Supplier_Name"),
            "invoice_no": extracted_data.get("Invoice_No"),
            "invoice_date": extracted_data.get("Invoice_Date")
        }
        
        # Update Neo4j Status -> DRAFT
        update_invoice_status(driver, invoice_id, "DRAFT", tenant_id, result_state)
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
        update_invoice_status(driver, invoice_id, "ERROR", tenant_id, error=str(e))
    finally:
        # cleanup
        if os.path.exists(local_path):
            os.remove(local_path)

async def enrich_invoice_items_background(normalized_items: list, user_email: str, tenant_id: str):
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
            MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name, tenant_id: $tenant_id})
            RETURN gp.manufacturer as m, gp.salt_composition as s
            """
            
            needs_enrichment = True
            with driver.session() as session:
                rec = session.execute_read(lambda tx: tx.run(check_query, user_email=user_email, name=product_name, tenant_id=tenant_id).single())
                if rec and rec["m"] and rec["m"] != "Unknown" and rec["s"]:
                     needs_enrichment = False
            
            if not needs_enrichment:
                logger.info(f"Skipping enrichment for {product_name} (Already present)")
                continue

            logger.info(f"Enriching Invoice Item: {product_name}")
            local_pack_size = item.get("Pack_Size_Description")
            local_mrp = item.get("MRP")
            result = await agent.enrich_product(product_name, local_pack_size=local_pack_size, local_mrp=local_mrp)
            
            if result.get("error"):
                logger.warning(f"Enrichment Error for {product_name}: {result['error']}")
                continue
                
            # Check if valid data was returned
            if not result.get("manufacturer") and not result.get("salt_composition"):
                logger.warning(f"Enrichment returned empty data for {product_name}. Skipping save.")
                continue

            # Update DB
            update_query = """
            MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name, tenant_id: $tenant_id})
            SET gp.manufacturer = $manufacturer,
                gp.salt_composition = $salt,
                gp.category = $category,
                gp.is_enriched = true,
                gp.needs_review = $needs_review,
                gp.pack_size_primary = $psp,
                gp.updated_at = timestamp()
            """
            
            with driver.session() as session:
                session.execute_write(lambda tx: tx.run(update_query, 
                            user_email=user_email,
                            name=product_name,
                            tenant_id=tenant_id,
                            manufacturer=result.get("manufacturer"),
                            salt=result.get("salt_composition"),
                            category=result.get("category"),
                            needs_review=result.get("needs_review", False),
                            psp=result.get("pack_size_primary", 1)))
                            
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
                MATCH (u:User {email: $user_email})-[:MANAGES]->(gp:GlobalProduct {name: $name, tenant_id: $tenant_id})
                SET gp.base_unit = $base_unit,
                    gp.unit_name = $base_unit
                """
                with driver.session() as session:
                    session.execute_write(lambda tx: tx.run(unit_update_query, 
                                user_email=user_email, 
                                name=product_name, 
                                tenant_id=tenant_id,
                                base_unit=new_base_unit))

        except Exception as e:
            logger.error(f"Failed to enrich item {product_name}: {e}")

