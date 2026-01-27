from typing import Dict, Any, List
import json
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

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
                 "is_duplicate": record["is_duplicate"], 
                 "duplicate_warning": record["duplicate_warning"],
                 "created_at": record["created_at"]
             })
        return invoices

def delete_draft_invoices(driver, user_email: str):
    """
    Deletes all invoices in PROCESSING, DRAFT, or ERROR state for the user.
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

def get_invoice_draft(driver, invoice_id: str):
    """
    Fetches the raw draft state of an invoice by ID.
    """
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id})
    RETURN i.raw_state as result
    """
    with driver.session() as session:
        record = session.run(query, invoice_id=invoice_id).single()
        if record and record["result"]:
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

def create_invoice_draft(driver, state: Dict[str, Any], user_email: str):
    pass

def _create_draft_tx(tx, invoice_no, supplier, state, user_email):
    pass

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
