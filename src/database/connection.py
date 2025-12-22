import os
from neo4j import GraphDatabase

# Singleton Driver
_DRIVER = None

def init_driver():
    global _DRIVER
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    try:
        _DRIVER = GraphDatabase.driver(uri, auth=(user, password))
        _DRIVER.verify_connectivity()
        print("Connected to Neo4j (Singleton).")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        _DRIVER = None

def get_driver():
    return _DRIVER

def close_driver():
    if _DRIVER:
        _DRIVER.close()
