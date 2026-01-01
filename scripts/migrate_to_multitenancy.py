
import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load env variables (Neo4j Credentials)
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

def migrate(target_email="admin@pharmagpt.co"):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    print(f"Starting Migration. Target User: {target_email}")
    
    try:
        with driver.session() as session:
            # 1. Create User Node if not exists
            print("1. Creating User Node...")
            session.run("""
                MERGE (u:User {email: $email})
                ON CREATE SET u.created_at = timestamp(), u.name = 'Admin User'
                RETURN u.email
            """, email=target_email)
            
            # 2. Assign Orphans (Invoices)
            print("2. Assigning Orphan Invoices...")
            result = session.run("""
                MATCH (u:User {email: $email})
                MATCH (i:Invoice)
                WHERE NOT (u)-[:OWNS]->(i)
                MERGE (u)-[:OWNS]->(i)
                RETURN count(i) as assigned_count
            """, email=target_email).single()
            print(f"   -> Assigned {result['assigned_count']} Invoices.")

            # 3. Assign Orphans (Suppliers)
            print("3. Assigning Orphan Suppliers...")
            result = session.run("""
                MATCH (u:User {email: $email})
                MATCH (s:Supplier)
                WHERE NOT (u)-[:OWNS]->(s)
                MERGE (u)-[:OWNS]->(s)
                RETURN count(s) as assigned_count
            """, email=target_email).single()
            print(f"   -> Assigned {result['assigned_count']} Suppliers.")

            # 4. Assign Orphans (Products)
            print("4. Assigning Orphan Products...")
            result = session.run("""
                MATCH (u:User {email: $email})
                MATCH (p:Product)
                WHERE NOT (u)-[:OWNS]->(p)
                MERGE (u)-[:OWNS]->(p)
                RETURN count(p) as assigned_count
            """, email=target_email).single()
            print(f"   -> Assigned {result['assigned_count']} Products.")
            
            print("Migration Complete.")

    except Exception as e:
        print(f"Migration Failed: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@pharmagpt.co"
    migrate(email)
