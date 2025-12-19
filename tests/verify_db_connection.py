import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load .env
load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

if not uri or not user or not password:
    print("❌ Missing Neo4j credentials in .env")
    sys.exit(1)

print(f"Connecting to: {uri}")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("✅ Connection Successful!")
    driver.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    sys.exit(1)
