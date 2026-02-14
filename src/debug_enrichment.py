
from dotenv import load_dotenv
import os
import json
from src.services.database import get_db_driver

load_dotenv()

def check_product_enrichment(product_name):
    driver = get_db_driver()
    query = """
    MATCH (u:User {email: 'pranavgupta1638@gmail.com'})-[r:MANAGES]->(gp:GlobalProduct {name: $name})
    RETURN gp.name, gp.manufacturer, gp.salt_composition, gp.is_enriched, gp.base_unit, r
    """
    
    with driver.session() as session:
        result = session.run(query, name=product_name).single()
        
    if result:
        print(f"Relationship Found!")
        print(f"Product: {result['gp.name']}")
        print(f"Manufacturer: {result['gp.manufacturer']}")
        print(f"Salt: {result['gp.salt_composition']}")
        print(f"Is Enriched: {result['gp.is_enriched']}")
        print(f"Base Unit: {result['gp.base_unit']}")
    else:
        print(f"Relationship User-[MANAGES]->Product '{product_name}' NOT FOUND.")
        
        # Check if product exists at all
        check_prod = "MATCH (gp:GlobalProduct {name: $name}) RETURN gp.name"
        with driver.session() as session:
            res = session.run(check_prod, name=product_name).single()
            if res:
                print(f"Product '{product_name}' EXISTS but is orphaned (no MANAGES relation).")
            else:
                print(f"Product '{product_name}' DOES NOT EXIST.")

if __name__ == "__main__":
    check_product_enrichment("LIVO-LUK SOLUTION 200ML")
