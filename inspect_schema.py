from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))

def print_schema():
    with driver.session() as session:
        print("--- Node Labels ---")
        result = session.run("CALL db.labels()")
        for record in result:
            print(record[0])
            
        print("\n--- Relationship Types ---")
        result = session.run("CALL db.relationshipTypes()")
        for record in result:
            print(record[0])
            
        print("\n--- Sample Data (Product <-> InventoryBatch) ---")
        # Try to find any relationship between InventoryBatch and Product
        result = session.run("""
            MATCH (b:InventoryBatch)-[r]-(p:Product) 
            RETURN type(r) as rel_type, properties(b) as batch_props, properties(p) as prod_props LIMIT 1
        """)
        record = result.single()
        if record:
            print(f"Relationship: {record['rel_type']}")
            print(f"Batch Props: {record['batch_props']}")
            print(f"Product Props: {record['prod_props']}")
        else:
            print("No relationship found between InventoryBatch and Product directly.")
            
        print("\n--- Sample Data (Any InventoryBatch) ---")
        result = session.run("MATCH (b:InventoryBatch) RETURN properties(b) as props LIMIT 1")
        record = result.single()
        if record:
            print(f"InventoryBatch Props: {record['props']}")

print_schema()
driver.close()
