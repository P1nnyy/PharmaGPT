
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
password = os.getenv("NEO4J_PASSWORD")

def list_invoices():
    print(f"Connecting to {uri} as {user}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Query Invoices by 'invoice_id' property (which corresponds to URL)
            res = session.run("MATCH (i:Invoice) RETURN i.invoice_id as id, i.filename as name, i.status as status ORDER BY i.created_at DESC LIMIT 10")
            for r in res:
                inv_id = r['id']
                print(f"{inv_id} | {r['name']} | {r['status']}")
                
                # Check for items using Line_Item and CONTAINS
                items = session.run("MATCH (i:Invoice {invoice_id: $id})-[:CONTAINS]->(li:Line_Item) RETURN count(li) as c", id=inv_id).single()
                print(f"  -> Items: {items['c']}")
        driver.close()
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    list_invoices()
