import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import get_db_driver

def check_invoice_pricing():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to Neo4j")
        return

    # Broad search to find the correct invoice first
    query = """
    MATCH (i:Invoice)-[:CONTAINS]->(li:Line_Item)
    MATCH (li)-[:IS_VARIANT_OF]->(gp:GlobalProduct)
    MATCH (li)-[:IS_PACKAGING_VARIANT]->(pv:PackagingVariant)
    RETURN i.invoice_number AS inv_no,
           gp.name AS product_name, 
           li.mrp AS line_mrp,
           pv.mrp AS variant_mrp,
           li.logic_note AS note,
           li.expiry_date AS expiry,
           li.batch_no AS batch
    ORDER BY i.invoice_number, gp.name
    """
    
    with driver.session() as session:
        result = session.run(query)
        print(f"{'Inv No':<10} | {'Product Name':<30} | {'L-MRP':<8} | {'V-MRP':<8} | {'Expiry':<8} | {'Note'}")
        print("-" * 110)
        for record in result:
            print(f"{str(record['inv_no']):<10} | {str(record['product_name']):<30} | {str(record['line_mrp']):<8} | {str(record['variant_mrp']):<8} | {str(record['expiry']):<8} | {str(record['note'])}")

if __name__ == "__main__":
    check_invoice_pricing()
