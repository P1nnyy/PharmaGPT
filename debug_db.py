
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j")
logger.setLevel(logging.DEBUG) # Enable debug logging for driver

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print(f"Testing connection to: {uri} with user: {user}")

try:
    # Try default first
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("SUCCESS: Default connection worked!")
    driver.close()
except Exception as e:
    print(f"FAILURE: Default connection failed: {e}")
    
    # Try with explicit encryption settings if first fails
    try:
        print("Retrying with encrypted=True and TRUST_SYSTEM_CA_SIGNED_CERTIFICATES...")
        driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=True, trust="TRUST_SYSTEM_CA_SIGNED_CERTIFICATES")
        driver.verify_connectivity()
        print("SUCCESS: Explicit encryption settings worked!")
        driver.close()
    except Exception as e2:
        print(f"FAILURE: Explicit encryption failed: {e2}")
