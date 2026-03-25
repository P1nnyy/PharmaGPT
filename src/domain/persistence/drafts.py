from typing import Dict, Any, List
import json
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def get_draft_invoices(driver, user_email: str):
    """
    Fetches invoices in PROCESSING, DRAFT, or ERROR state for the user.
    """
    query = """
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
    WITH u, s
    
    MATCH (i:Invoice)
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
      AND (
        (u)-[:OWNS]->(i) OR
        (s IS NOT NULL AND (i)-[:BELONGS_TO]->(s))
      )
    
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
    def _read_drafts(tx):
        result = tx.run(query, user_email=user_email)
        invoices = []
        for record in result:
             res_json = record["result"]
             res_data = json.loads(res_json) if res_json else None
             
             invoices.append({
                 "id": record["id"],
                 "filename": record["filename"],
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

    with driver.session() as session:
        return session.execute_read(_read_drafts)

def delete_draft_invoices(driver, user_email: str):
    """
    Deletes all invoices in PROCESSING, DRAFT, or ERROR state for the user.
    """
    query = """
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
    WITH u, s
    
    MATCH (i:Invoice)
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
      AND (
        (u)-[:OWNS]->(i) OR
        (s IS NOT NULL AND (i)-[:BELONGS_TO]->(s))
      )
    
    WITH i, count(i) as cnt
    DETACH DELETE i
    RETURN sum(cnt) as cnt
    """
    try:
        def _delete_tx(tx):
            result = tx.run(query, user_email=user_email).single()
            return result["cnt"] if result else 0

        with driver.session() as session:
            count = session.execute_write(_delete_tx)
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
    def _read_tx(tx):
        record = tx.run(query, invoice_id=invoice_id).single()
        if record and record["result"]:
            return json.loads(record["result"])
        return None

    with driver.session() as session:
        return session.execute_read(_read_tx)

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

def delete_invoice_by_id(driver, invoice_id: str, user_email: str, wipe: bool = False, is_admin: bool = False):
    """
    Deletes a specific invoice by ID.
    If wipe=True, performs a cascading delete of all associated line items and correction history.
    If is_admin=True, bypasses ownership checks.
    """
    if wipe:
        # Cascading Deep Wipe
        if is_admin:
            query = """
            MATCH (i:Invoice {invoice_id: $invoice_id})
            OPTIONAL MATCH (i)-[:CONTAINS]->(li:Line_Item)
            OPTIONAL MATCH (i)-[:HAS_CORRECTION]->(cs:CorrectionSet)
            OPTIONAL MATCH (cs)-[:INCLUDES]->(diff:Diff)
            WITH i, collect(distinct li) as lis, collect(distinct cs) as css, collect(distinct diff) as diffs
            DETACH DELETE i
            WITH lis, css, diffs
            UNWIND (lis + css + diffs) as x
            DETACH DELETE x
            """
        else:
            query = """
            MATCH (u:User {email: $user_email})
            OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
            WITH u, s
            
            MATCH (i:Invoice {invoice_id: $invoice_id})
            WHERE (
                (u)-[:OWNS]->(i) OR
                (s IS NOT NULL AND (i)-[:BELONGS_TO]->(s))
            )
            
            OPTIONAL MATCH (i)-[:CONTAINS]->(li:Line_Item)
            OPTIONAL MATCH (i)-[:HAS_CORRECTION]->(cs:CorrectionSet)
            OPTIONAL MATCH (cs)-[:INCLUDES]->(diff:Diff)
            WITH i, collect(distinct li) as lis, collect(distinct cs) as css, collect(distinct diff) as diffs
            DETACH DELETE i
            WITH lis, css, diffs
            UNWIND (lis + css + diffs) as x
            DETACH DELETE x
            """
        logger.info(f"PERFORMING {'ADMIN ' if is_admin else ''}DEEP WIPE for Invoice {invoice_id}")
    else:
        # Standard Shallow Delete
        if is_admin:
            query = """
            MATCH (i:Invoice {invoice_id: $invoice_id})
            DETACH DELETE i
            """
        else:
            query = """
            MATCH (u:User {email: $user_email})
            OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
            WITH u, s
            
            MATCH (i:Invoice {invoice_id: $invoice_id})
            WHERE (
                (u)-[:OWNS]->(i) OR
                (s IS NOT NULL AND (i)-[:BELONGS_TO]->(s))
            )
            DETACH DELETE i
            """
        logger.info(f"Performing {'admin ' if is_admin else ''}shallow delete for Invoice {invoice_id}")

    with driver.session() as session:
        session.execute_write(lambda tx: tx.run(query, user_email=user_email, invoice_id=invoice_id))

def delete_redundant_draft(driver, invoice_id: str, user_email: str):
    """
    Safely deletes a draft invoice ONLY if it has not been confirmed.
    This handles cases where the draft remains after a new node was created for the confirmed invoice.
    If the draft node itself was updated to CONFIRMED, it will be skipped (preserved).
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_id: $invoice_id})
    WHERE i.status <> 'CONFIRMED'
    DETACH DELETE i
    RETURN count(i) as deleted_count
    """
    try:
        def _delete_tx(tx):
            result = tx.run(query, user_email=user_email, invoice_id=invoice_id).single()
            return result["deleted_count"] if result else 0

        with driver.session() as session:
            count = session.execute_write(_delete_tx)
            if count > 0:
                logger.info(f"SUCCESS: Deleted redundant draft {invoice_id} for {user_email}.")
            else:
                logger.info(f"SKIPPED: Draft {invoice_id} not deleted. Count={count}. (Status might be CONFIRMED or ID mismatch)")
    except Exception as e:
        logger.error(f"Failed to delete redundant draft {invoice_id}: {e}")
