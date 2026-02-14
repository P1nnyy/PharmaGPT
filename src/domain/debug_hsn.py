
from src.services.database import get_db_driver
import logging

logging.basicConfig(level=logging.INFO)

def check_hsn_consistency():
    driver = get_db_driver()
    if not driver:
        print("No DB Driver")
        return

    query = """
    MATCH (n:GlobalProduct)
    RETURN n.name as Name, n.hsn_code as HSN, n.item_code as SKU
    ORDER BY n.name
    """
    
    print(f"{'Name':<40} | {'HSN':<10} | {'SKU':<10}")
    print("-" * 65)
    
    with driver.session() as session:
        result = session.run(query)
        for record in result:
            print(f"{record['Name'][:38]:<40} | {str(record['HSN']):<10} | {str(record['SKU']):<10}")

if __name__ == "__main__":
    check_hsn_consistency()
