
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import sys

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

def check_invoice(invoice_id):
    print(f"Checking Invoice {invoice_id} in {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Check Invoice Node
        inv = session.run("MATCH (i:Invoice {id: $id}) RETURN i.status as status, i.filename as name", id=invoice_id).single()
        if inv:
            print(f"Invoice Found: {inv['name']} | Status: {inv['status']}")
        else:
            print("Invoice NOT found!")
            return

        # Check Items
        items = session.run("MATCH (i:Invoice {id: $id})-[:HAS_ITEM]->(li:LineItem) RETURN count(li) as c").single()
        print(f"LineItems Count: {items['c']}")
        
        # Check relationships to GlobalProduct
        mapped = session.run("MATCH (i:Invoice {id: $id})-[:HAS_ITEM]->(li:LineItem)-[:MAPS_TO]->(gp:GlobalProduct) RETURN count(gp) as c").single()
        print(f"Mapped Items Count: {mapped['c']}")
        
    driver.close()

if __name__ == "__main__":
    inv_id = sys.argv[1] if len(sys.argv) > 1 else "ef05159132cbeffa824ab099d6cf2595"
    check_invoice(inv_id)
