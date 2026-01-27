from typing import List, Dict, Any, Optional
import json
from src.utils.logging_config import get_logger
from src.domain.schemas import InvoiceExtraction
from src.services.embeddings import generate_embedding
from src.domain.persistence.inventory import _create_line_item_tx
from src.domain.persistence.access import _merge_supplier_tx
from neo4j.exceptions import ClientError

logger = get_logger(__name__)

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
    Updates the status of an existing Invoice node.
    """
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
        check_query = """
        MATCH (other:Invoice {invoice_number: $invoice_no})
        WHERE other.invoice_id <> $invoice_id
        RETURN count(other) as cnt
        """
        dup_result = tx.run(check_query, invoice_no=invoice_no, invoice_id=invoice_id).single()
        if dup_result and dup_result["cnt"] > 0:
            # Duplicate found!
            query = """
            MATCH (i:Invoice {invoice_id: $invoice_id})
            SET i.status = 'DRAFT',
                i.updated_at = timestamp(),
                i.is_duplicate = true,
                i.duplicate_warning = 'Invoice ' + $invoice_no + ' already exists.'
                
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
        i.is_duplicate = false 
        
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

def _mark_duplicate_tx(tx, invoice_id, result_state):
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

def _create_invoice_example_tx(tx, supplier, raw_text, json_payload, embedding):
    query = """
    MERGE (ex:InvoiceExample {raw_text: $raw_text})
    SET ex.supplier = $supplier,
        ex.json_payload = $json_payload,
        ex.embedding = $embedding,
        ex.created_at = timestamp()
    """
    tx.run(query, supplier=supplier, raw_text=raw_text, json_payload=json_payload, embedding=embedding)
