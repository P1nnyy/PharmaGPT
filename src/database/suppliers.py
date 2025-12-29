from typing import List, Dict, Any

def get_supplier_history(driver) -> List[Dict[str, Any]]:
    """
    Returns a list of Suppliers, each with their invoices.
    """
    query = """
    MATCH (s:Supplier)
    OPTIONAL MATCH (s)-[:ISSUED]->(i:Invoice)
    WITH s, i ORDER BY i.created_at DESC
    WITH s, collect({
        invoice_number: i.invoice_number,
        date: i.invoice_date,
        total: i.grand_total,
        status: i.status,
        image_path: i.image_path
    }) as invoices
    RETURN s.name as name, s.gst as gst, s.phone as phone, invoices
    ORDER BY name ASC
    """
    with driver.session() as session:
        result = session.run(query)
        data = []
        for record in result:
            valid_invoices = [inv for inv in record["invoices"] if inv["invoice_number"]]
            
            # Calculate Total Spend
            total_spend = sum(float(inv["total"] or 0) for inv in valid_invoices)

            row = {
                "name": record["name"],
                "gst": record["gst"],
                "phone": record["phone"],
                "total_spend": total_spend,
                "invoices": valid_invoices
            }
            data.append(row)
        return data
