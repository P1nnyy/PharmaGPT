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
        status: i.status
    }) as invoices
    RETURN s.name as name, s.gst as gst, s.phone as phone, invoices
    ORDER BY name ASC
    """
    with driver.session() as session:
        result = session.run(query)
        data = []
        for record in result:
            row = {
                "name": record["name"],
                "gst": record["gst"],
                "phone": record["phone"],
                # Filter out null invoices
                "invoices": [inv for inv in record["invoices"] if inv["invoice_number"]]
            }
            data.append(row)
        return data
