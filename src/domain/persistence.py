from typing import List, Dict, Any, Optional
from src.domain.schemas import InvoiceExtraction, NormalizedLineItem
from src.domain.normalization import parse_float
import os
import json
import re
from src.utils.logging_config import get_logger
from src.services.embeddings import generate_embedding

logger = get_logger(__name__)

def init_db_constraints(driver):
    """
    Ensures unique constraints exist for GlobalProduct item_code.
    """
    query = "CREATE CONSTRAINT item_code_unique IF NOT EXISTS FOR (p:GlobalProduct) REQUIRE p.item_code IS UNIQUE"
    try:
        with driver.session() as session:
            session.run(query)
            logger.info("Checked/Created Unique Constraint for GlobalProduct.item_code")
    except Exception as e:
        logger.error(f"Failed to create constraint: {e}")

def _generate_sku(tx, product_name: str) -> str:
    """
    Generates a Name-Based SKU (e.g., 'DOL-001') using a transactional counter.
    Format: AAA-NNN (First 3 letters of name - Sequential Number)
    """
    if not product_name:
        return "UNK-000"
        
    # 1. Extract Prefix (First 3 uppercase letters)
    clean_name = re.sub(r'[^a-zA-Z]', '', product_name).upper()
    prefix = (clean_name[:3] if len(clean_name) >= 3 else clean_name.ljust(3, 'X'))
    
    # 2. Atomically Increment Counter for this Prefix
    query = """
    MERGE (c:SkuCounter {prefix: $prefix})
    SET c.current_count = coalesce(c.current_count, 0) + 1
    RETURN c.current_count as num
    """
    result = tx.run(query, prefix=prefix).single()
    count = result["num"]
    
    # 3. Format SKU
    return f"{prefix}-{count:03d}"

def upsert_user(driver, user_data: Dict[str, Any]):
    """
    Creates or updates a User node based on Google OAuth data.
    """
    query = """
    MERGE (u:User {email: $email})
    SET u.google_id = $google_id,
        u.name = $name,
        u.picture = $picture,
        u.updated_at = timestamp()
    RETURN u
    """
    with driver.session() as session:
        session.run(query, 
                    email=user_data.get("email"),
                    google_id=user_data.get("google_id"),
                    name=user_data.get("name"),
                    picture=user_data.get("picture"))

def ingest_invoice(driver, invoice_data: InvoiceExtraction, normalized_items: List[Dict[str, Any]], user_email: str, supplier_details: Dict[str, Any] = None):
    """
    Ingests invoice and line item data into Neo4j, scoped to a specific User.
    Also merges detailed Supplier information if available.
    """
    
    # Calculate Grand Total from line items to ensure consistency
    grand_total = 0.0
    for item in normalized_items:
        try:
            val = float(item.get("Net_Line_Amount", 0.0))
        except (ValueError, TypeError):
            val = 0.0
        grand_total += val
    
    try:
        with driver.session() as session:
            # 1. Merge Invoice (Scoped to User)
            session.execute_write(_create_invoice_tx, invoice_data, grand_total, user_email)
            
            # 2. Merge Separate Supplier Node (Rich Data, Scoped to User)
            if supplier_details:
                # Ensure name matches the Invoice's supplier name for consistency
                supplier_name = invoice_data.Supplier_Name
                session.execute_write(_merge_supplier_tx, supplier_name, supplier_details, user_email)
            
            # 3. Process Line Items
            # Clean up existing line items if re-ingesting to prevent duplicates
            session.run("MATCH (i:Invoice {invoice_number: $no})-[r:CONTAINS]->(l:Line_Item) DELETE r, l", no=invoice_data.Invoice_No)

            # Process each item using the atomic transaction
            for raw_item, item in zip(invoice_data.Line_Items, normalized_items):
                session.execute_write(_create_line_item_tx, invoice_data.Invoice_No, item, raw_item, user_email)
                
            # 4. Save Invoice Example for RAG (Few-Shot)
            if invoice_data.raw_text:
                logger.info("Generating Vector Embedding for Invoice Example...")
                try:
                    json_payload = invoice_data.model_dump_json() if hasattr(invoice_data, 'model_dump_json') else invoice_data.json()
                    embedding = generate_embedding(invoice_data.raw_text)
                    if embedding:
                        session.execute_write(
                            _create_invoice_example_tx, 
                            invoice_data.Supplier_Name, 
                            invoice_data.raw_text, 
                            json_payload, 
                            embedding
                        )
                except Exception as e:
                    logger.error(f"Failed to save Invoice Example: {e}")

    except Exception as e:
        logger.error(f"Detailed Ingestion Error for Invoice {invoice_data.Invoice_No}: {e}")
        raise e

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any, user_email: str):
    query = """
    MATCH (u:User {email: $user_email})
    MATCH (u)-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    
    // 1. Alias Lookup & Product Resolution
    OPTIONAL MATCH (alias:ProductAlias {raw_name: $standard_item_name})-[:MAPS_TO]->(master:GlobalProduct)
    
    // Determine final name: Use Master if alias found, else use incoming name
    WITH coalesce(master.name, $standard_item_name) as final_product_name, u, i
    
    // 2. Merge Global Product
    MERGE (gp:GlobalProduct {name: final_product_name})
    
    // Ensure User manages this product
    MERGE (u)-[:MANAGES]->(gp)
    
    ON CREATE SET 
        gp.is_verified = false,
        gp.needs_review = true,
        gp.created_at = timestamp()
        
    // ----------------------------------------------------
    // ATOMIC SKU GENERATION (Name-Based: AAA-NNN)
    // ----------------------------------------------------
    WITH gp, u, i,
         toUpper(substring(replace(final_product_name, ' ', ''), 0, 3)) as raw_p
    
    WITH gp, u, i,
         CASE WHEN size(raw_p) < 3 THEN raw_p + substring("XXX", 0, 3 - size(raw_p)) ELSE raw_p END as prefix
         
    // Conditional Lock & Increment if item_code is missing
    FOREACH (_ IN CASE WHEN gp.item_code IS NULL THEN [1] ELSE [] END |
        MERGE (c:SkuCounter {prefix: prefix})
        SET c.current_count = coalesce(c.current_count, 0) + 1
        SET gp.item_code = prefix + "-" + right("000" + toString(c.current_count), 3)
    )
    // ----------------------------------------------------
    
    // 3. Merge HSN Node
    MERGE (h:HSN {code: $hsn_code})
    
    // 4. Create Line Item
    CREATE (l:Line_Item {
        pack_size: $pack_size,
        quantity: $quantity,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note,
        
        // Pharma Fields
        salt: $salt,
        category: $category,
        manufacturer: $manufacturer,
        unit_1st: $unit_1st,
        unit_2nd: $unit_2nd,
        sales_rate_a: $sales_rate_a,
        sales_rate_b: $sales_rate_b,
        sales_rate_c: $sales_rate_c,
        sgst_percent: $sgst_percent,
        cgst_percent: $cgst_percent,
        igst_percent: $igst_percent
    })
    
    // 5. Connect Graph
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
    
    // 6. Multi-Unit Packaging Tracking
    MERGE (pv:PackagingVariant {pack_size: $pack_size, product_name: final_product_name})
    MERGE (gp)-[:HAS_VARIANT]->(pv)
    MERGE (l)-[:IS_PACKAGING_VARIANT]->(pv)
    
    ON CREATE SET
        pv.unit_name = $unit_2nd,
        pv.mrp = $mrp,
        pv.conversion_factor = 1,
        pv.created_at = timestamp(),
        gp.needs_review = true
        
    ON MATCH SET
        pv.mrp = $mrp,
        pv.updated_at = timestamp()
        
    // 7. Update Master Data with latest pricing
    SET gp.sale_price = coalesce($mrp, gp.sale_price),
        gp.purchase_price = coalesce($rate, gp.purchase_price),
        gp.tax_rate = coalesce($total_tax_rate, gp.tax_rate),
        gp.hsn_code = coalesce($hsn_code, gp.hsn_code)
    """
    
    logger.info(f"DEBUG_TX: Ingesting '{item.get('Standard_Item_Name')}' (Pack: {item.get('Pack_Size_Description')})")
    
    # Calculate Total Tax %
    s = item.get("SGST_Percent") or 0.0
    c = item.get("CGST_Percent") or 0.0
    i = item.get("IGST_Percent") or 0.0
    total_tax_rate = s + c + i
    
    tx.run(query,
           user_email=user_email,
           invoice_no=invoice_no,
           standard_item_name=item.get("Standard_Item_Name"),
           pack_size=item.get("Pack_Size_Description") or "1x1",
           quantity=item.get("Standard_Quantity"),
           net_amount=item.get("Net_Line_Amount"),
           batch_no=item.get("Batch_No"),
           hsn_code=item.get("HSN_Code") or "UNKNOWN", 
           mrp=item.get("MRP", 0.0),
           rate=item.get("Rate", 0.0),
           total_tax_rate=total_tax_rate,
           expiry_date=item.get("Expiry_Date"),
           landing_cost=item.get("Final_Unit_Cost", 0.0),
           logic_note=item.get("Logic_Note", "N/A"),
           
           salt=item.get("Salt"),
           category=item.get("Category"),
           manufacturer=item.get("Manufacturer"),
           unit_1st=item.get("Unit_1st"),
           unit_2nd=item.get("Unit_2nd"),
           sales_rate_a=item.get("Sales_Rate_A"),
           sales_rate_b=item.get("Sales_Rate_B"),
           sales_rate_c=item.get("Sales_Rate_C"),
           sgst_percent=item.get("SGST_Percent"),
           cgst_percent=item.get("CGST_Percent"),
           igst_percent=item.get("IGST_Percent")
    )


def _merge_supplier_tx(tx, name, details, user_email):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (s:Supplier {name: $name})
    
    // Create ownership if not exists
    MERGE (u)-[:OWNS]->(s)
    
    SET s.address = $address,
        s.gstin = $gstin,
        s.dl_no = $dl_no,
        s.phone = $phone,
        s.email = $email,
        s.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           name=name,
           address=details.get("Address"),
           gstin=details.get("GSTIN"),
           dl_no=details.get("DL_No"),
           phone=details.get("Phone_Number"),
           email=details.get("Email")
    )

def create_processing_invoice(driver, invoice_id: str, filename: str, image_path: str, user_email: str):
    """
    Creates an initial Invoice node with status 'PROCESSING'.
    Used for immediate feedback before analysis completes.
    """
    with driver.session() as session:
        session.execute_write(_create_processing_tx, invoice_id, filename, image_path, user_email)

def _create_processing_tx(tx, invoice_id, filename, image_path, user_email):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (i:Invoice {invoice_id: $invoice_id})
    MERGE (u)-[:OWNS]->(i)
    
    ON CREATE SET 
        i.status = 'PROCESSING',
        i.filename = $filename,
        i.image_path = $image_path,
        i.created_at = timestamp(),
        i.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           invoice_id=invoice_id,
           filename=filename,
           image_path=image_path)

def update_invoice_status(driver, invoice_id: str, status: str, result_state: Dict[str, Any] = None, error: str = None):
    """
    Updates the status of an existing Invoice node (e.g. PROCESSING -> DRAFT).
    Backfills extracted data if available.
    """
    from neo4j.exceptions import ClientError
    
    try:
        with driver.session() as session:
            session.execute_write(_update_status_tx, invoice_id, status, result_state, error)
            
    except ClientError as e:
        if "ConstraintValidationFailed" in str(e) and "invoice_number" in str(e):
             # Detected Duplicate Constraint Violation!
             # Fallback: Update status to DRAFT (Success) but mark as Duplicate
             logger.warning(f"Constraint Violation for Invoice {invoice_id}. Marking as Duplicate.")
             with driver.session() as session:
                 session.execute_write(_mark_duplicate_tx, invoice_id, result_state)
        else:
             # Re-raise other Neo4j errors
             raise e

def _update_status_tx(tx, invoice_id, status, result_state, error):
    # Serialize state
    import json
    state_json = json.dumps(result_state, default=str) if result_state else None
    
    # Extract high-level fields if available for the Node connection/display
    invoice_no = result_state.get("invoice_data", {}).get("Invoice_No") if result_state else None
    supplier = result_state.get("invoice_data", {}).get("Supplier_Name") if result_state else None
    grand_total = result_state.get("invoice_data", {}).get("Stated_Grand_Total") if result_state else None
    
    # Check for duplicate Invoice Number
    if invoice_no:
        # Check if ANOTHER node (not this one) has this invoice_number
        check_query = """
        MATCH (other:Invoice {invoice_number: $invoice_no})
        WHERE other.invoice_id <> $invoice_id
        RETURN count(other) as cnt
        """
        dup_result = tx.run(check_query, invoice_no=invoice_no, invoice_id=invoice_id).single()
        if dup_result and dup_result["cnt"] > 0:
            # Duplicate found!
            # SOFT WARNING: Mark as DRAFT but add a flag.
            # We append a validation flag to the serialized state if possible, or just set a node property.
            
            # Inject into state_json (deserializing if needed, or string manip? No, we have result_state dict passed in context usually, but here it's serialized... wait.)
            # Actually, the parameters to run() are static. 
            # We can set a property on the node `is_duplicate = true`.
            
            # Note: We continue to execute the main UPDATE query below, but adding the duplicate flag.
            
            query = """
            MATCH (i:Invoice {invoice_id: $invoice_id})
            SET i.status = 'DRAFT',  // Success, but warn
                i.updated_at = timestamp(),
                i.is_duplicate = true,   // New Flag
                i.duplicate_warning = 'Invoice ' + $invoice_no + ' already exists.'
                
            // Conditionally Update Fields
            // NOTE: Do NOT set i.invoice_number here to avoid ConstraintViolation
            FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
                SET i.raw_state = $state_json,
                    i.supplier_name = coalesce($supplier, i.supplier_name),
                    i.grand_total = coalesce($grand_total, i.grand_total)
            )
            """
            tx.run(query,
                   invoice_id=invoice_id,
                   invoice_no=invoice_no,
                   supplier=supplier,
                   grand_total=grand_total,
                   state_json=state_json)
            return

    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id})
    SET i.status = $status,
        i.updated_at = timestamp(),
        i.is_duplicate = false // Clear flag if re-processed/corrected
        
    // Conditionally Update Fields if provided
    FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
        SET i.raw_state = $state_json,
            i.invoice_number = coalesce($invoice_no, i.invoice_number),
            i.supplier_name = coalesce($supplier, i.supplier_name),
            i.grand_total = coalesce($grand_total, i.grand_total)
    )
    
    FOREACH (_ IN CASE WHEN $error IS NOT NULL THEN [1] ELSE [] END |
        SET i.error_message = $error
    )
    """
    tx.run(query,
           invoice_id=invoice_id,
           status=status,
           state_json=state_json,
           error=error,
           invoice_no=invoice_no,
           supplier=supplier,
           grand_total=grand_total)

def get_draft_invoices(driver, user_email: str):
    """
    Fetches invoices in PROCESSING, DRAFT, or ERROR state for the user.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
    RETURN i.invoice_id as id,
           i.filename as filename,
           i.status as status,
           i.image_path as image_path,
           i.raw_state as result,
           i.error_message as error,
           i.is_duplicate as is_duplicate,
           i.duplicate_warning as duplicate_warning,
           i.created_at as created_at
    ORDER BY i.created_at DESC
    """
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        invoices = []
        for record in result:
             # Deserialize result JSON if present
             res_json = record["result"]
             res_data = json.loads(res_json) if res_json else None
             
             invoices.append({
                 "id": record["id"],
                 "file": {"name": record["filename"]}, 
                 "status": record["status"].lower(), 
                 "previewUrl": record["image_path"],
                 "result": res_data,
                 "error": record["error"],
                 "is_duplicate": record["is_duplicate"], # New Field
                 "duplicate_warning": record["duplicate_warning"], # New Field
                 "created_at": record["created_at"]
             })
        return invoices

def get_invoice_draft(driver, invoice_id: str):
    """
    Fetches the raw draft state of an invoice by ID.
    Used for comparing Original vs Final changes.
    """
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id})
    RETURN i.raw_state as result
    """
    with driver.session() as session:
        record = session.run(query, invoice_id=invoice_id).single()
        if record and record["result"]:
            import json
            return json.loads(record["result"])
        return None

def log_correction(driver, invoice_id: str, original: Dict[str, Any], final: Dict[str, Any], user_email: str):
    """
    Logs the differences between Original (Draft) and Final (Confirmed) invoice data.
    """
    changes = []
    
    # 1. Header Changes
    for field in ["Invoice_No", "Invoice_Date", "Supplier_Name", "Stated_Grand_Total", "Global_Discount_Amount"]:
        old_val = original.get("invoice_data", {}).get(field)
        new_val = final.get(field)
        
        # Simple normalization for comparison (str)
        if str(old_val) != str(new_val) and new_val is not None:
             changes.append({
                 "field": field,
                 "old": str(old_val),
                 "new": str(new_val),
                 "type": "header"
             })

    # 2. Supplier Details Changes
    old_supp = original.get("invoice_data", {}).get("supplier_details", {}) or {}
    new_supp = final.get("supplier_details", {}) or {}
    
    for field in ["GSTIN", "DL_No", "Address", "Phone_Number"]:
        old_val = old_supp.get(field)
        new_val = new_supp.get(field)
        if str(old_val) != str(new_val) and new_val is not None:
             changes.append({
                 "field": f"supplier.{field}",
                 "old": str(old_val),
                 "new": str(new_val),
                 "type": "supplier"
             })

    if not changes:
        return

    # 3. Store Corrections in Graph
    with driver.session() as session:
        session.execute_write(_create_correction_nodes_tx, invoice_id, changes, user_email)

def _create_correction_nodes_tx(tx, invoice_id, changes, user_email):
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id})
    MATCH (u:User {email: $user_email})
    
    MERGE (c:CorrectionSet {id: $change_id})
    ON CREATE SET 
        c.created_at = timestamp(),
        c.count = size($changes)
        
    MERGE (i)-[:HAS_CORRECTION]->(c)
    MERGE (c)-[:MADE_BY]->(u)
    
    FOREACH (change IN $changes |
        CREATE (d:Diff {
            field: change.field,
            old_value: change.old,
            new_value: change.new,
            type: change.type
        })
        CREATE (c)-[:INCLUDES]->(d)
    )
    """
    import uuid
    change_id = uuid.uuid4().hex
    tx.run(query, invoice_id=invoice_id, changes=changes, user_email=user_email, change_id=change_id)

def delete_draft_invoices(driver, user_email: str):
    """
    Deletes all invoices in PROCESSING, DRAFT, or ERROR state for the user.
    Used for 'Clear All' functionality.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
    WITH i, count(i) as cnt
    DETACH DELETE i
    RETURN cnt
    """
    try:
        with driver.session() as session:
            result = session.run(query, user_email=user_email).single()
            count = result["cnt"] if result else 0
            logger.info(f"Deleted {count} draft invoices for {user_email}.")
    except Exception as e:
        logger.error(f"Failed to delete drafts for {user_email}: {e}")
        raise e

def create_invoice_draft(driver, state: Dict[str, Any], user_email: str):
    """
    Creates a DRAFT invoice node in Neo4j, scoped to a User.
    Used for Staging before full confirmation.
    """
    # Legacy wrapper or specific use case? 
    # For now keeping it but our new flow uses create_processing -> update
    pass

def _create_draft_tx(tx, invoice_no, supplier, state, user_email):
    # Keeping for compatibility if needed, but likely replaced
    pass

def _create_invoice_tx(tx, invoice_data: InvoiceExtraction, grand_total: float, user_email: str):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier_name})
    MERGE (u)-[:OWNS]->(i)
    
    ON CREATE SET 
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.created_at = timestamp()
    ON MATCH SET
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           invoice_no=invoice_data.Invoice_No, 
           supplier_name=invoice_data.Supplier_Name,
           invoice_date=invoice_data.Invoice_Date,
           grand_total=grand_total,
           image_path=invoice_data.image_path)

def link_product_alias(driver, user_email: str, master_product_name: str, raw_alias: str):
    """
    Links a raw product name (alias) to a Master GlobalProduct.
    """
    with driver.session() as session:
        session.execute_write(_link_alias_tx, user_email, master_product_name, raw_alias)

def _link_alias_tx(tx, user_email, master_product_name, raw_alias):
    query = """
    MATCH (u:User {email: $user_email})
    
    // Find Master Product (must exist and be managed by user or globally available)
    MATCH (gp:GlobalProduct {name: $master_name})
    // Optional: Check if User manages it? For now, assuming Global lookup.
    
    // Create Alias Node
    MERGE (alias:ProductAlias {raw_name: $raw_alias})
    
    // Link Alias to Master
    MERGE (alias)-[:MAPS_TO]->(gp)
    
    // Link to User? Maybe later to track who created the alias.
    """
    tx.run(query, user_email=user_email, master_name=master_product_name, raw_alias=raw_alias)

def rename_product_with_alias(driver, user_email: str, old_name: str, new_name: str):
    """
    Renames a GlobalProduct or Merges it if the new name already exists.
    In both cases, creates a ProductAlias for the old name pointing to the new name.
    """
    with driver.session() as session:
        session.execute_write(_rename_product_tx, user_email, old_name, new_name)

def _rename_product_tx(tx, user_email, old_name, new_name):
    # Check if target exists (Merge Case vs Rename Case)
    check_q = "MATCH (gp:GlobalProduct {name: $new_name}) RETURN count(gp) as cnt"
    target_exists = tx.run(check_q, new_name=new_name).single()["cnt"] > 0
    
    if target_exists:
        # MERGE CASE: Repoint & Delete Old
        logger.info(f"Merging '{old_name}' into existing '{new_name}'")
        query = """
        MATCH (u:User {email: $user_email})
        MATCH (old:GlobalProduct {name: $old_name})
        MATCH (new:GlobalProduct {name: $new_name})
        
        // 1. Repoint Alias links (Aliases pointing to Old now point to New)
        OPTIONAL MATCH (alias:ProductAlias)-[r1:MAPS_TO]->(old)
        DELETE r1
        MERGE (alias)-[:MAPS_TO]->(new)
        
        // 2. Repoint Line Items (History)
        OPTIONAL MATCH (li:Line_Item)-[r2:IS_VARIANT_OF]->(old)
        DELETE r2
        MERGE (li)-[:IS_VARIANT_OF]->(new)
        
        // 3. Repoint Packaging Variants
        // (If new product already has similar variants, this might create dupes on the node, 
        //  but visually distinct variants. Ideally we merge same-size variants but that's complex.
        //  Simple link for now.)
        OPTIONAL MATCH (old)-[r3:HAS_VARIANT]->(v:PackagingVariant)
        DELETE r3
        MERGE (new)-[:HAS_VARIANT]->(v)
        // Update variant product_name property
        SET v.product_name = $new_name
        
        // 4. Create Alias for the Old Name itself
        MERGE (self_alias:ProductAlias {raw_name: $old_name})
        MERGE (self_alias)-[:MAPS_TO]->(new)
        
        // 5. Delete Old Node
        DETACH DELETE old
        """
        tx.run(query, user_email=user_email, old_name=old_name, new_name=new_name)
        
    else:
        # RENAME CASE: Just update name and create alias
        logger.info(f"Renaming '{old_name}' to new '{new_name}'")
        query = """
        MATCH (u:User {email: $user_email})
        MATCH (gp:GlobalProduct {name: $old_name})
        
        // 1. Create Alias for Old Name
        MERGE (alias:ProductAlias {raw_name: $old_name})
        MERGE (alias)-[:MAPS_TO]->(gp)
        
        // 2. Update Product Name
        SET gp.name = $new_name,
            gp.updated_at = timestamp()
            
        // 3. Update related PackagingVariants' product_name property
        WITH gp
        OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant)
        SET pv.product_name = $new_name
        """
        tx.run(query, user_email=user_email, old_name=old_name, new_name=new_name)

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any, user_email: str):
    query = """
    MATCH (u:User {email: $user_email})
    MATCH (u)-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    
    // 1. Alias Lookup & Product Resolution
    // Check if the incoming name is a known alias
    OPTIONAL MATCH (alias:ProductAlias {raw_name: $standard_item_name})-[:MAPS_TO]->(master:GlobalProduct)
    
    // Determine final name: Use Master if alias found, else use incoming name
    WITH coalesce(master.name, $standard_item_name) as final_product_name, u, i
    
    // 2. Merge Global Product
    MERGE (gp:GlobalProduct {name: final_product_name})
    
    // Ensure User manages this product (ownership/access)
    MERGE (u)-[:MANAGES]->(gp)
    
    ON CREATE SET 
        gp.is_verified = false,
        gp.needs_review = true,
        gp.created_at = timestamp()
    
    // 2. Merge HSN Node
    MERGE (h:HSN {code: $hsn_code})
    
    // 3. Create Line Item (Specific Variant / Instance)
    CREATE (l:Line_Item {
        pack_size: $pack_size,
        quantity: $quantity,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note,
        
        // New Pharma Fields
        salt: $salt,
        category: $category,
        manufacturer: $manufacturer,
        unit_1st: $unit_1st,
        unit_2nd: $unit_2nd,
        sales_rate_a: $sales_rate_a,
        sales_rate_b: $sales_rate_b,
        sales_rate_c: $sales_rate_c,
        sgst_percent: $sgst_percent,
        cgst_percent: $cgst_percent,
        igst_percent: $igst_percent
    })
    
    // 4. Connect Graph
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
    
    // 5. Multi-Unit Packaging Tracking
    MERGE (pv:PackagingVariant {pack_size: $pack_size, product_name: final_product_name})
    MERGE (gp)-[:HAS_VARIANT]->(pv)
    MERGE (l)-[:IS_PACKAGING_VARIANT]->(pv)
    
    ON CREATE SET
        pv.unit_name = $unit_2nd,
        pv.mrp = $mrp,
        pv.conversion_factor = 1,
        pv.created_at = timestamp(),
        gp.needs_review = true
        
    ON MATCH SET
        pv.mrp = $mrp,
        pv.updated_at = timestamp()
        
    // 6. UPDATE MASTER DATA (GlobalProduct) with latest pricing
    // Moved to end to avoid breaking MERGE (pv) ... ON CREATE flow
    SET gp.sale_price = coalesce($mrp, gp.sale_price),
        gp.purchase_price = coalesce($rate, gp.purchase_price),
        gp.tax_rate = coalesce($total_tax_rate, gp.tax_rate),
        gp.hsn_code = coalesce($hsn_code, gp.hsn_code)
    """

    
    logger.info(f"DEBUG_TX: Linking Variant pack_size={item.get('Pack_Size_Description')} to product={item.get('Standard_Item_Name')}")
    
    # Calculate Total Tax %
    s = item.get("SGST_Percent") or 0.0
    c = item.get("CGST_Percent") or 0.0
    i = item.get("IGST_Percent") or 0.0
    total_tax_rate = s + c + i
    
    tx.run(query,
           user_email=user_email,
           invoice_no=invoice_no,
           standard_item_name=item.get("Standard_Item_Name"),
           pack_size=item.get("Pack_Size_Description") or "1x1",
           quantity=item.get("Standard_Quantity"),
           net_amount=item.get("Net_Line_Amount"),
           batch_no=item.get("Batch_No"),
           hsn_code=item.get("HSN_Code") or "UNKNOWN", 
           mrp=item.get("MRP", 0.0),
           rate=item.get("Rate", 0.0), # Pass Rate
           total_tax_rate=total_tax_rate, # Pass Tax
           expiry_date=item.get("Expiry_Date"),
           landing_cost=item.get("Final_Unit_Cost", 0.0),
           logic_note=item.get("Logic_Note", "N/A"),
           
           # New Pharma Fields Mapped
           salt=item.get("Salt"),
           category=item.get("Category"),
           manufacturer=item.get("Manufacturer"),
           unit_1st=item.get("Unit_1st"),
           unit_2nd=item.get("Unit_2nd"),
           sales_rate_a=item.get("Sales_Rate_A"),
           sales_rate_b=item.get("Sales_Rate_B"),
           sales_rate_c=item.get("Sales_Rate_C"),
           sgst_percent=item.get("SGST_Percent"),
           cgst_percent=item.get("CGST_Percent"),
           igst_percent=item.get("IGST_Percent")
    )

def get_activity_log(driver, user_email: str):
    """
    Fetches the last 20 processed invoices for the dashboard history, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status = 'CONFIRMED'
    OPTIONAL MATCH (u)-[:OWNS]->(s:Supplier {name: i.supplier_name})
    RETURN i.invoice_number as invoice_number, 
           i.supplier_name as supplier_name, 
           i.created_at as created_at, 
           i.grand_total as total,
           i.image_path as image_path,
           s.gstin as supplier_gst,
           s.phone as supplier_phone,
           s.dl_no as supplier_dl,
           s.address as supplier_address,
           u.name as saved_by
    ORDER BY i.created_at DESC LIMIT 20
    """
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

def get_inventory(driver, user_email: str):
    """
    Fetches aggregated inventory data for the dashboard, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)-[:CONTAINS]->(l:Line_Item)
    MATCH (l)-[:IS_VARIANT_OF]->(gp:GlobalProduct)
    RETURN gp.name as product_name, 
           sum(l.quantity) as total_quantity, 
           max(l.mrp) as mrp
    ORDER BY total_quantity DESC
    """
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

def get_invoice_details(driver, invoice_no, user_email: str):
    """
    Fetches full invoice details and line items, checking User ownership.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (u)-[:OWNS]->(s:Supplier {name: i.supplier_name})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:IS_VARIANT_OF]->(p:GlobalProduct)
    RETURN i, s, collect({
        line: l, 
        product: p 
    }) as items
    """
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no, user_email=user_email).single()
        
    if not result:
        return None
        
    invoice_node = dict(result["i"])
    supplier_node = dict(result["s"]) if result["s"] else {}
    
    # Merge supplier info into invoice dict for convenience
    invoice_data = {**invoice_node}
    invoice_data["supplier_phone"] = supplier_node.get("phone")
    invoice_data["supplier_gst"] = supplier_node.get("gstin")
    invoice_data["supplier_address"] = supplier_node.get("address")
    invoice_data["supplier_dl"] = supplier_node.get("dl_no")
    
    line_items = []
    for item in result["items"]:
        l_node = dict(item["line"]) if item["line"] else {}
        p_node = dict(item["product"]) if item["product"] else {}
        
        # Construct flat item dict
        line_item = {
            **l_node,
            "product_name": (p_node.get("name") or l_node.get("raw_description") or "Unknown Item")
        }
        line_items.append(line_item)
        
    return {
        "invoice": invoice_data,
        "line_items": line_items
    }

def get_grouped_invoice_history(driver, user_email: str):
    """
    Fetches invoices grouped by Supplier for the History View.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status = 'CONFIRMED'
    
    // Group by Supplier Name
    WITH i.supplier_name as supplier_name, collect(i) as invoices, u.name as user_name
    
    // Calculate total spend per supplier
    // (Ensure grand_total is treated as float)
    WITH supplier_name, invoices, user_name,
         reduce(msg = 0.0, inv in invoices | msg + coalesce(inv.grand_total, 0.0)) as total_spend
         
    RETURN supplier_name, total_spend, invoices, user_name
    ORDER BY total_spend DESC
    """
    
    data = []
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        
        for record in result:
            supplier_name = record["supplier_name"]
            total_spend = record["total_spend"]
            invoice_nodes = record["invoices"]
            user_name = record["user_name"]
            
            # Format invoices list
            formatted_invoices = []
            for node in invoice_nodes:
                inv = dict(node)
                formatted_invoices.append({
                    "invoice_number": inv.get("invoice_number"),
                    "date": inv.get("invoice_date"),
                    "total": inv.get("grand_total"),
                    "image_path": inv.get("image_path") # Ensure we capture image path if stored on Invoice node
                })
                
            # Sort invoices by date (newest first)
            # Assuming date format is sortable or just rely on DB order if we added ORDER BY in collect (complex in one query)
            # Let's sort in python
            formatted_invoices.sort(key=lambda x: x.get("date") or "", reverse=True)
            
            data.append({
                "name": supplier_name,
                "total_spend": total_spend,
                "invoices": formatted_invoices,
                "saved_by": user_name
            })
            
    return data

def _create_invoice_example_tx(tx, supplier_name: str, raw_text: str, json_payload: str, embedding: List[float]):
    """
    Creates an InvoiceExample node linked to the Supplier.
    Stores the raw text, verified JSON, and the vector embedding.
    """
    query = """
    MATCH (s:Supplier {name: $supplier_name})
    
    CREATE (e:InvoiceExample {
        raw_text: $raw_text,
        json_payload: $json_payload,
        created_at: timestamp()
    })
    
    // Store embedding as a Vector property (Neo4j 5.x+)
    SET e.embedding = $embedding
    
    // Link to Supplier (One Supplier has many Examples)
    MERGE (s)-[:HAS_EXAMPLE]->(e)
    """
    tx.run(query, 
           supplier_name=supplier_name, 
           raw_text=raw_text, 
           json_payload=json_payload, 
           embedding=embedding)



def _mark_duplicate_tx(tx, invoice_id, result_state):
    """
    Fallback transaction when Unique Constraint on invoice_number is violated.
    Marks the invoice as DRAFT (Warning) instead of failing.
    """
    import json
    state_json = json.dumps(result_state, default=str) if result_state else None
    invoice_no = result_state.get("invoice_data", {}).get("Invoice_No") if result_state else "Unknown"
    supplier = result_state.get("invoice_data", {}).get("Supplier_Name") if result_state else None
    grand_total = result_state.get("invoice_data", {}).get("Stated_Grand_Total") if result_state else None
    
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id})
    SET i.status = 'DRAFT',
        i.updated_at = timestamp(),
        i.is_duplicate = true,
        i.duplicate_warning = 'Invoice ' + $invoice_no + ' already exists.'
        
    // Save state but DO NOT set invoice_number
    FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
        SET i.raw_state = $state_json,
            i.supplier_name = coalesce($supplier, i.supplier_name),
            i.grand_total = coalesce($grand_total, i.grand_total)
    )
    """
    tx.run(query, 
           invoice_id=invoice_id,
           invoice_no=invoice_no,
           state_json=state_json, 
           supplier=supplier,
           grand_total=grand_total)



def delete_invoice_by_id(driver, invoice_id: str, user_email: str):
    """
    Deletes a specific invoice by ID.
    Used for 'Discard' menu action.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_id: $invoice_id})
    DETACH DELETE i
    """
    with driver.session() as session:
        session.run(query, user_email=user_email, invoice_id=invoice_id)

def delete_redundant_draft(driver, invoice_id: str, user_email: str):
    """
    Safely deletes a draft invoice ONLY if it is still in DRAFT/PROCESSING state.
    Used during confirmation to clean up if a new node was created instead of updating.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_id: $invoice_id})
    WHERE i.status IN ['DRAFT', 'PROCESSING', 'ERROR']
    DETACH DELETE i
    """
    with driver.session() as session:
        session.run(query, user_email=user_email, invoice_id=invoice_id)
