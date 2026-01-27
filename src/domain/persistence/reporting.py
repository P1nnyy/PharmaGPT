from typing import List, Dict, Any, Optional
import json
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

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
