from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))

def apply_schema():
    with open("schema_upgrade.cypher", "r") as f:
        queries = f.read().split(";")
    
    with driver.session() as session:
        for query in queries:
            query = query.strip()
            if query and not query.startswith("//"):
                print(f"Running: {query[:50]}...")
                try:
                    session.run(query)
                except Exception as e:
                    print(f"Error running query: {e}")

if __name__ == "__main__":
    apply_schema()
    driver.close()
    print("Schema upgrade complete.")
