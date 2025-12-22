from typing import List, Dict, Any

def get_inventory_aggregation(driver) -> List[Dict[str, Any]]:
    """
    Returns inventory aggregated by Product Name + MRP.
    Calculates Total Quantity (Stock).
    """
    query = """
    MATCH (l:Line_Item)-[:REFERENCES]->(p:Product)
    WITH p.name as product_name, l.mrp as mrp, sum(l.quantity) as total_qty, collect(l.batch_no) as batches
    RETURN product_name, mrp, total_qty, batches
    ORDER BY product_name ASC
    """
    with driver.session() as session:
        result = session.run(query)
        return [
            {
                "product_name": record["product_name"],
                "mrp": record["mrp"],
                "total_quantity": record["total_qty"],
                "batches": list(set(record["batches"])) 
            }
            for record in result
        ]
