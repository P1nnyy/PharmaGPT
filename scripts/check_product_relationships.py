
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.services.database import get_db_driver

def check_relationships():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    with driver.session() as session:
        # 1. Total Global Products
        result = session.run("MATCH (gp:GlobalProduct) RETURN count(gp) as total")
        total_products = result.single()["total"]
        print(f"Total GlobalProduct Nodes: {total_products}")

        # 2. Managed Products (linked to ANY user)
        result = session.run("MATCH (u:User)-[:MANAGES]->(gp:GlobalProduct) RETURN count(distinct gp) as managed")
        managed_products = result.single()["managed"]
        print(f"Products managed by a User: {managed_products}")

        # 3. Unmanaged (Orphan) Products
        orphans = total_products - managed_products
        print(f"Orphan Products (Not linked to User): {orphans}")

        if orphans > 0:
            print("\nSAMPLE ORPHANS:")
            result = session.run("MATCH (gp:GlobalProduct) WHERE NOT (:User)-[:MANAGES]->(gp) RETURN gp.name as name LIMIT 5")
            for record in result:
                print(f"- {record['name']}")

if __name__ == "__main__":
    check_relationships()
