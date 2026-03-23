from typing import List, Dict, Any, Optional
import json
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def get_activity_log(driver, user_email: str):
    """
    Fetches the last 20 processed invoices for the dashboard history, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
    WITH u, s
    
    MATCH (inv:Invoice)
    WHERE inv.status = 'CONFIRMED'
      AND (
        (s IS NOT NULL AND (inv)-[:BELONGS_TO]->(s)) OR
        (s IS NULL AND (u)-[:OWNS]->(inv))
      )
    
    OPTIONAL MATCH (u)-[:OWNS]->(supp:Supplier {name: inv.supplier_name})
    
    // Get the User who OWNS this invoice
    OPTIONAL MATCH (owner:User)-[:OWNS]->(inv)
    
    RETURN inv.invoice_id as id,
           inv.invoice_number as invoice_number, 
           coalesce(inv.supplier_name, 'Unknown Supplier') as supplier_name, 
           inv.created_at as created_at, 
           inv.updated_at as saved_at,
           coalesce(inv.grand_total, 0.0) as total,
           inv.image_path as image_path,
           supp.gstin as supplier_gst,
           supp.phone as supplier_phone,
           supp.dl_no as supplier_dl,
           supp.address as supplier_address,
           coalesce(owner.name, 'User') as saved_by
    ORDER BY inv.updated_at DESC LIMIT 20
    """
    with driver.session() as session:
        return session.execute_read(lambda tx: [
            {**dict(record), 
             "supplier_name": record["supplier_name"] or "Unknown Supplier",
             "total": record["total"] or 0.0,
             "saved_by": record["saved_by"] or "User"} 
            for record in tx.run(query, user_email=user_email)
        ])

def get_inventory(driver, user_email: str):
    """
    Fetches aggregated inventory data for the dashboard, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
    WITH u, s
    
    MATCH (inv:Invoice)-[:CONTAINS]->(l:Line_Item)
    WHERE inv.status = 'CONFIRMED'
      AND (
        (s IS NOT NULL AND (inv)-[:BELONGS_TO]->(s)) OR
        (s IS NULL AND (u)-[:OWNS]->(inv))
      )
      
    MATCH (l)-[:IS_VARIANT_OF]->(gp:GlobalProduct)
    RETURN gp.name as product_name, 
           sum(l.quantity) as total_quantity, 
           max(l.mrp) as mrp
    ORDER BY total_quantity DESC
    """
    with driver.session() as session:
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, user_email=user_email)])

def get_invoice_details(driver, invoice_no, user_email: str):
    """
    Fetches full invoice details and line items, checking User ownership.
    """
    query = """
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
    WITH u, s
    
    MATCH (inv:Invoice {invoice_number: $invoice_no})
    WHERE (
        (s IS NOT NULL AND (inv)-[:BELONGS_TO]->(s)) OR
        (s IS NULL AND (u)-[:OWNS]->(inv))
    )
    
    OPTIONAL MATCH (u)-[:OWNS]->(supp:Supplier {name: inv.supplier_name})
    OPTIONAL MATCH (inv)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:IS_VARIANT_OF]->(p:GlobalProduct)
    RETURN inv, supp, collect({
        line: l, 
        product: p 
    }) as items
    """
    with driver.session() as session:
        result = session.execute_read(lambda tx: tx.run(query, invoice_no=invoice_no, user_email=user_email).single())
        
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
    MATCH (u:User {email: $user_email})
    OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s_node:Shop)
    WITH u, s_node
    
    MATCH (inv:Invoice)
    WHERE inv.status = 'CONFIRMED'
      AND (
        (s_node IS NOT NULL AND (inv)-[:BELONGS_TO]->(s_node)) OR
        (s_node IS NULL AND (u)-[:OWNS]->(inv))
      )
    
    // Group by Supplier Name
    WITH coalesce(inv.supplier_name, 'Unknown Supplier') as supplier_name, inv
    
    // Get the User who OWNS this invoice
    OPTIONAL MATCH (owner:User)-[:OWNS]->(inv)
    
    WITH supplier_name, 
         inv, 
         coalesce(owner.name, 'Unknown') as uploader_name,
         coalesce(owner.email, '') as uploader_email
    
    WITH supplier_name, 
         collect({
            id: inv.invoice_id,
            invoice_number: inv.invoice_number,
            date: inv.invoice_date,
            uploaded_at: inv.created_at,
            saved_at: inv.updated_at,
            total: coalesce(inv.grand_total, 0.0),
            image_path: inv.image_path,
            saved_by: uploader_name,
            saved_by_email: uploader_email
         }) as inv_details
         
    // Calculate total spend per supplier
    WITH supplier_name, inv_details,
         reduce(msg = 0.0, entry in inv_details | msg + entry.total) as total_spend
         
    RETURN supplier_name, total_spend, inv_details
    ORDER BY total_spend DESC
    """
    
    with driver.session() as session:
        def _read_history(tx):
            result = tx.run(query, user_email=user_email)
            data = []
            for record in result:
                supplier_name = record["supplier_name"]
                total_spend = record["total_spend"]
                invoices = record["inv_details"]
                
                # Sort invoices by date
                invoices.sort(key=lambda x: x.get("date") or "", reverse=True)
                
                data.append({
                    "name": supplier_name,
                    "total_spend": total_spend,
                    "invoices": invoices
                })
            return data

        return session.execute_read(_read_history)
