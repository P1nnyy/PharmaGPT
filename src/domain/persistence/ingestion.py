from typing import List, Dict, Any, Optional
import json
from src.utils.logging_config import get_logger
from src.domain.schemas import InvoiceExtraction
from src.services.embeddings import generate_embedding
from src.domain.persistence.inventory import _ingest_line_items_batch_tx
from src.domain.persistence.access import _merge_supplier_tx
from neo4j.exceptions import ClientError

logger = get_logger(__name__)

def ingest_invoice(driver, invoice_id: str, invoice_data: InvoiceExtraction, normalized_items: List[Dict[str, Any]], shop_id: str, tenant_id: str, supplier_details: Dict[str, Any] = None):
    """
    Ingests invoice and line item data into Neo4j, anchored to a Shop.
    """
    
    # Use the finalized grand total from the extraction object
    grand_total = getattr(invoice_data, 'grand_total', 0.0)
    
    def _full_ingestion_tx(tx):
        # 1. Update/Merge Invoice (Scoped to Shop)
        _create_invoice_tx(tx, invoice_id, invoice_data, grand_total, shop_id, tenant_id)
        
        # 2. Merge Separate Supplier Node (Can still keep user_email for audit if needed, but shop is anchor)
        if supplier_details:
            supplier_name = invoice_data.Supplier_Name
            _merge_supplier_tx(tx, supplier_name, supplier_details, shop_id, tenant_id)
        
        # 3. Clean up existing line items for this specific invoice
        tx.run("MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})-[r:CONTAINS]->(l:Line_Item) DETACH DELETE l", 
               shop_id=shop_id, invoice_id=invoice_id, tenant_id=tenant_id)

        # 4. Process all items in a single batch transaction
        _ingest_line_items_batch_tx(tx, invoice_data.Invoice_No, normalized_items, shop_id, tenant_id, invoice_id=invoice_id)

    try:
        with driver.session() as session:
            session.execute_write(_full_ingestion_tx)
            logger.info(f"Successfully ingested invoice {invoice_data.Invoice_No} and {len(normalized_items)} line items.")

    except Exception as e:
        logger.error(f"Detailed Ingestion Error for Invoice {invoice_data.Invoice_No}: {e}")
        raise e

def _create_invoice_tx(tx, invoice_id: str, invoice_data: InvoiceExtraction, grand_total: float, shop_id: str, tenant_id: str):
    query = """
    MATCH (s:Shop {id: $shop_id})
    MATCH (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    
    // Ensure this Shop owns it
    MERGE (s)-[:HAS_INVOICE]->(i)
    
    SET i.status = 'CONFIRMED',
        i.invoice_number = $invoice_no,
        i.supplier_name = $supplier_name,
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.tenant_id = $tenant_id,
        i.updated_at = timestamp()
    """
    tx.run(query, 
           shop_id=shop_id,
           invoice_id=invoice_id,
           tenant_id=tenant_id,
           invoice_no=invoice_data.Invoice_No, 
           supplier_name=invoice_data.Supplier_Name,
           invoice_date=invoice_data.Invoice_Date,
           grand_total=grand_total,
           image_path=invoice_data.image_path)

def create_processing_invoice(driver, invoice_id: str, filename: str, image_path: str, shop_id: str, tenant_id: str):
    """
    Creates an initial Invoice node with status 'PROCESSING', anchored to a Shop.
    """
    with driver.session() as session:
        session.execute_read(lambda tx: tx.run("MERGE (s:Shop {id: $id})", id=shop_id)) # Ensure shop exists
        session.execute_write(_create_processing_tx, invoice_id, filename, image_path, shop_id, tenant_id)

def _create_processing_tx(tx, invoice_id, filename, image_path, shop_id, tenant_id):
    query = """
    MATCH (s:Shop {id: $shop_id})
    MERGE (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    ON CREATE SET 
        i.status = 'PROCESSING',
        i.filename = $filename,
        i.image_path = $image_path,
        i.tenant_id = $tenant_id,
        i.created_at = timestamp(),
        i.updated_at = timestamp()
        
    MERGE (s)-[:HAS_INVOICE]->(i)
    """
    tx.run(query, 
           shop_id=shop_id,
           invoice_id=invoice_id,
           tenant_id=tenant_id,
           filename=filename,
           image_path=image_path)

def update_invoice_status(driver, invoice_id: str, status: str, tenant_id: str, result_state: Dict[str, Any] = None, error: str = None, status_message: str = None):
    """
    Updates the status of an existing Invoice node, scoped to a tenant.
    """
    try:
        with driver.session() as session:
            session.execute_write(_update_status_tx, invoice_id, status, tenant_id, result_state, error, status_message)
            
    except ClientError as e:
        if "ConstraintValidationFailed" in str(e) and "invoice_number" in str(e):
             logger.warning(f"Constraint Violation for Invoice {invoice_id}. Marking as Duplicate.")
             with driver.session() as session:
                 session.execute_write(_mark_duplicate_tx, invoice_id, tenant_id, result_state)
        else:
             raise e

def _update_status_tx(tx, invoice_id, status, tenant_id, result_state, error, status_message):
    # Serialize state
    import json
    state_json = json.dumps(result_state, default=str) if result_state else None
    
    # Extract high-level fields if available for the Node connection/display
    # Check top level first, then inside invoice_data for robustness
    image_path = result_state.get("image_path") or result_state.get("invoice_data", {}).get("image_path") if result_state else None
    invoice_no = result_state.get("invoice_no") or result_state.get("invoice_data", {}).get("Invoice_No") if result_state else None
    supplier = result_state.get("supplier_name") or result_state.get("invoice_data", {}).get("Supplier_Name") if result_state else None
    grand_total = result_state.get("grand_total") or result_state.get("invoice_data", {}).get("Stated_Grand_Total") if result_state else None
    
    # Check for duplicate Invoice Number (Scoped to Tenant)
    if invoice_no:
        check_query = """
        MATCH (other:Invoice {invoice_number: $invoice_no, tenant_id: $tenant_id})
        WHERE other.invoice_id <> $invoice_id
        RETURN count(other) as cnt
        """
        dup_result = tx.run(check_query, invoice_no=invoice_no, invoice_id=invoice_id, tenant_id=tenant_id).single()
        if dup_result and dup_result["cnt"] > 0:
            # Duplicate found!
            query = """
            MATCH (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
            SET i.status = 'DRAFT',
                i.updated_at = timestamp(),
                i.is_duplicate = true,
                i.duplicate_warning = 'Invoice ' + $invoice_no + ' already exists.'
                
            FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
                SET i.raw_state = $state_json,
                    i.supplier_name = coalesce($supplier, i.supplier_name),
                    i.grand_total = coalesce($grand_total, i.grand_total),
                    i.image_path = coalesce($image_path, i.image_path)
            )
            """
            tx.run(query,
                   invoice_id=invoice_id,
                   tenant_id=tenant_id,
                   invoice_no=invoice_no,
                   supplier=supplier,
                   grand_total=grand_total,
                   state_json=state_json,
                   image_path=image_path)
            return

    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    SET i.status = $status,
        i.updated_at = timestamp(),
        i.is_duplicate = false 
        
    FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
        SET i.raw_state = $state_json,
            i.invoice_number = coalesce($invoice_no, i.invoice_number),
            i.supplier_name = coalesce($supplier, i.supplier_name),
            i.grand_total = coalesce($grand_total, i.grand_total),
            i.image_path = coalesce($image_path, i.image_path)
    )
    
    FOREACH (_ IN CASE WHEN $error IS NOT NULL THEN [1] ELSE [] END |
        SET i.error_message = $error
    )
    
    FOREACH (_ IN CASE WHEN $status_message IS NOT NULL THEN [1] ELSE [] END |
        SET i.status_message = $status_message
    )
    """
    result = tx.run(query,
                   invoice_id=invoice_id,
                   tenant_id=tenant_id,
                   status=status,
                   state_json=state_json,
                   error=error,
                   status_message=status_message,
                   invoice_no=invoice_no,
                   supplier=supplier,
                   grand_total=grand_total,
                   image_path=image_path)
    summary = result.consume()
    logger.info(f"Updated status for {invoice_id} to {status}. Nodes updated: {summary.counters.properties_set}")

def _mark_duplicate_tx(tx, invoice_id, tenant_id, result_state):
    import json
    state_json = json.dumps(result_state, default=str) if result_state else None
    invoice_no = result_state.get("invoice_data", {}).get("Invoice_No") if result_state else "Unknown"
    supplier = result_state.get("invoice_data", {}).get("Supplier_Name") if result_state else None
    grand_total = result_state.get("invoice_data", {}).get("Stated_Grand_Total") if result_state else None
    
    image_path = result_state.get("image_path") or result_state.get("invoice_data", {}).get("image_path") if result_state else None
    
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    SET i.status = 'DRAFT',
        i.updated_at = timestamp(),
        i.is_duplicate = true,
        i.duplicate_warning = 'Invoice ' + $invoice_no + ' already exists.'
        
    FOREACH (_ IN CASE WHEN $state_json IS NOT NULL THEN [1] ELSE [] END |
        SET i.raw_state = $state_json,
            i.supplier_name = coalesce($supplier, i.supplier_name),
            i.grand_total = coalesce($grand_total, i.grand_total),
            i.image_path = coalesce($image_path, i.image_path)
    )
    """
    tx.run(query, 
           invoice_id=invoice_id,
           tenant_id=tenant_id,
           invoice_no=invoice_no,
           state_json=state_json, 
           supplier=supplier,
           grand_total=grand_total,
           image_path=image_path)

def _create_invoice_example_tx(tx, supplier, raw_text, json_payload, embedding):
    query = """
    MERGE (ex:InvoiceExample {raw_text: $raw_text})
    SET ex.supplier = $supplier,
        ex.json_payload = $json_payload,
        ex.embedding = $embedding,
        ex.created_at = timestamp()
    """
    tx.run(query, supplier=supplier, raw_text=raw_text, json_payload=json_payload, embedding=embedding)

def index_invoice_for_rag(driver, invoice_data: InvoiceExtraction):
    """
    Background Task: Indexed the invoice for RAG (Few-Shot Support).
    This is slow (network calls for embeddings) so it should run in background.
    """
    if not invoice_data.raw_text:
        return
        
    logger.info(f"BACKGROUND_TASK: Generating Vector Embedding for Invoice Indexing: {invoice_data.Invoice_No}")
    try:
        json_payload = invoice_data.model_dump_json() if hasattr(invoice_data, 'model_dump_json') else invoice_data.json()
        embedding = generate_embedding(invoice_data.raw_text)
        if embedding:
            with driver.session() as session:
                session.execute_write(
                    _create_invoice_example_tx, 
                    invoice_data.Supplier_Name, 
                    invoice_data.raw_text, 
                    json_payload, 
                    embedding
                )
        logger.info(f"BACKGROUND_TASK: Indexed invoice {invoice_data.Invoice_No} successfully.")
    except Exception as e:
        logger.error(f"BACKGROUND_TASK: Failed to index Invoice Example: {e}")
