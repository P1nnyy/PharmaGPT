import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Add parent dir to path to find src if needed, but we essentially just need the driver
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

def migrate_suppliers():
    print(f"Connecting to {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    query = """
    MATCH (i:Invoice)
    WHERE i.supplier_name IS NOT NULL
    MERGE (s:Supplier {name: i.supplier_name})
    MERGE (s)-[:ISSUED]->(i)
    RETURN count(s) as created
    """
    
    try:
        with driver.session() as session:
            result = session.run(query)
            record = result.single()
            print(f"Migration Complete. Linked/Created Suppliers for {record['created']} relationships.")
            
    except Exception as e:
        print(f"Migration Failed: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    migrate_suppliers()
