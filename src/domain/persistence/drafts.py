from typing import Dict, Any, List
import json
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def get_draft_invoices(driver, shop_id: str, tenant_id: str, role: str = "Employee"):
    """
    Fetches invoices in PROCESSING, DRAFT, or ERROR state for the shop.
    Anchored to Shop for collaboration.
    """
    query = """
    MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {tenant_id: $tenant_id})
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
    
    RETURN i.invoice_id as id,
           i.filename as filename,
           i.status as status,
           i.image_path as image_path,
           i.raw_state as result,
           i.error_message as error,
           i.status_message as status_message,
           i.is_duplicate as is_duplicate,
           i.duplicate_warning as duplicate_warning,
           i.created_at as created_at
    ORDER BY i.created_at DESC
    """
    def _read_drafts(tx):
        result = tx.run(query, shop_id=shop_id, tenant_id=tenant_id)
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
                  "status_message": record["status_message"],
                  "is_duplicate": record["is_duplicate"], 
                  "duplicate_warning": record["duplicate_warning"],
                  "created_at": record["created_at"]
             })
        return invoices

    with driver.session() as session:
        return session.execute_read(_read_drafts)

def delete_draft_invoices(driver, shop_id: str, tenant_id: str):
    """
    Deletes all invoices in PROCESSING, DRAFT, or ERROR state for the shop.
    """
    query = """
    MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {tenant_id: $tenant_id})
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
    
    WITH i, count(i) as cnt
    DETACH DELETE i
    RETURN sum(cnt) as cnt
    """
    try:
        def _delete_tx(tx):
            result = tx.run(query, shop_id=shop_id, tenant_id=tenant_id).single()
            return result["cnt"] if result else 0

        with driver.session() as session:
            count = session.execute_write(_delete_tx)
            logger.info(f"Deleted {count} draft invoices for shop {shop_id}.")
    except Exception as e:
        logger.error(f"Failed to delete drafts for shop {shop_id}: {e}")
        raise e

def get_invoice_draft(driver, invoice_id: str, tenant_id: str):
    """
    Fetches the raw draft state of an invoice.
    """
    query = """
    MATCH (i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    RETURN i.raw_state as result
    """
    def _read_tx(tx):
        record = tx.run(query, invoice_id=invoice_id, tenant_id=tenant_id).single()
        if record and record["result"]:
            return json.loads(record["result"])
        return None

    with driver.session() as session:
        return session.execute_read(_read_tx)

def log_correction(driver, invoice_id: str, original: Dict[str, Any], final: Dict[str, Any], user_email: str, shop_id: str):
    """
    Logs corrections made by a user for an invoice in a shop.
    """
    changes = []
    
    # Header Changes
    for field in ["Invoice_No", "Invoice_Date", "Supplier_Name", "Stated_Grand_Total", "Global_Discount_Amount"]:
        old_val = original.get("invoice_data", {}).get(field)
        new_val = final.get(field)
        if str(old_val) != str(new_val) and new_val is not None:
             changes.append({
                 "field": field,
                 "old": str(old_val),
                 "new": str(new_val),
                 "type": "header"
             })

    if not changes:
        return

    tenant_id = final.get("tenant_id") or original.get("tenant_id")
    with driver.session() as session:
        session.execute_write(_create_correction_nodes_tx, invoice_id, changes, user_email, shop_id, tenant_id)

def _create_correction_nodes_tx(tx, invoice_id, changes, user_email, shop_id, tenant_id):
    query = """
    MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
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
    tx.run(query, invoice_id=invoice_id, changes=changes, user_email=user_email, shop_id=shop_id, tenant_id=tenant_id, change_id=change_id)

def delete_invoice_by_id(driver, invoice_id: str, shop_id: str, tenant_id: str, wipe: bool = False, is_admin: bool = False):
    """
    Deletes a specific invoice for a shop.
    """
    if wipe:
        query = """
        MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {tenant_id: $tenant_id})
        WHERE i.invoice_id = $invoice_id OR (i.invoice_number = $invoice_no AND $invoice_no IS NOT NULL)
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
        MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {tenant_id: $tenant_id})
        WHERE i.invoice_id = $invoice_id OR (i.invoice_number = $invoice_no AND $invoice_no IS NOT NULL)
        DETACH DELETE i
        """

    with driver.session() as session:
        def _delete_tx(tx):
            invoice_no = invoice_id if (invoice_id and len(invoice_id) < 10) else None
            result = tx.run(query, shop_id=shop_id, tenant_id=tenant_id, invoice_id=invoice_id, invoice_no=invoice_no)
            summary = result.consume()
            logger.info(f"Deletion for Invoice {invoice_id} in Shop {shop_id} completed. Nodes deleted: {summary.counters.nodes_deleted}")
            return summary.counters.nodes_deleted

        session.execute_write(_delete_tx)

def delete_redundant_draft(driver, invoice_id: str, shop_id: str, tenant_id: str):
    """
    Safely deletes a draft invoice.
    """
    query = """
    MATCH (s:Shop {id: $shop_id})-[:HAS_INVOICE]->(i:Invoice {invoice_id: $invoice_id, tenant_id: $tenant_id})
    WHERE i.status <> 'CONFIRMED'
    DETACH DELETE i
    RETURN count(i) as deleted_count
    """
    try:
        def _delete_tx(tx):
            result = tx.run(query, shop_id=shop_id, invoice_id=invoice_id, tenant_id=tenant_id).single()
            return result["deleted_count"] if result else 0

        with driver.session() as session:
            count = session.execute_write(_delete_tx)
            logger.info(f"Deleted {count} redundant drafts for shop {shop_id}.")
    except Exception as e:
        logger.error(f"Failed to delete redundant draft {invoice_id}: {e}")
