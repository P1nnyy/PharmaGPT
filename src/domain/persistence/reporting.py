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
    RETURN inv.invoice_number as invoice_number, 
           inv.supplier_name as supplier_name, 
           inv.created_at as created_at, 
           inv.updated_at as saved_at,
           inv.grand_total as total,
           inv.image_path as image_path,
           supp.gstin as supplier_gst,
           supp.phone as supplier_phone,
           supp.dl_no as supplier_dl,
           supp.address as supplier_address,
           u.name as saved_by
    ORDER BY inv.updated_at DESC LIMIT 20
    """
    with driver.session() as session:
        return session.execute_read(lambda tx: [dict(record) for record in tx.run(query, user_email=user_email)])

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
    WITH inv.supplier_name as supplier_name, collect(inv) as invoices, u.name as user_name
    
    // Calculate total spend per supplier
    WITH supplier_name, invoices, user_name,
         reduce(msg = 0.0, inver in invoices | msg + coalesce(inver.grand_total, 0.0)) as total_spend
         
    RETURN supplier_name, total_spend, invoices, user_name
    ORDER BY total_spend DESC
    """
    
    with driver.session() as session:
        def _read_history(tx):
            result = tx.run(query, user_email=user_email)
            data = []
            for record in result:
                supplier_name = record["supplier_name"]
                total_spend = record["total_spend"]
                invoice_nodes = record["invoices"]
                user_name = record["user_name"]
                
                formatted_invoices = []
                for node in invoice_nodes:
                    inv = dict(node)
                    formatted_invoices.append({
                        "invoice_number": inv.get("invoice_number"),
                        "date": inv.get("invoice_date"),
                        "uploaded_at": inv.get("created_at"),
                        "saved_at": inv.get("updated_at"),
                        "total": inv.get("grand_total"),
                        "image_path": inv.get("image_path")
                    })
                    
                formatted_invoices.sort(key=lambda x: x.get("date") or "", reverse=True)
                
                data.append({
                    "name": supplier_name,
                    "total_spend": total_spend,
                    "invoices": formatted_invoices,
                    "saved_by": user_name
                })
            return data

        return session.execute_read(_read_history)
