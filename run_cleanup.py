from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))

def run_cleanup():
    with open("cleanup_duplicates.cypher", "r") as f:
        query = f.read()
    
    with driver.session() as session:
        print("Running cleanup query...")
        result = session.run(query)
        record = result.single()
        if record:
            print(f"Cleanup complete. Merged {record['merged_products_count']} product groups.")
        else:
            print("Cleanup complete. No duplicates found.")

if __name__ == "__main__":
    run_cleanup()
    driver.close()
