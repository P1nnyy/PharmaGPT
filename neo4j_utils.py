import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Neo4jConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jConnection, cls).__new__(cls)
            cls._instance.driver = None
        return cls._instance

    def __init__(self):
        if self.driver is None:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD")
            
            if not password:
                raise ValueError("NEO4J_PASSWORD not found in environment variables.")
                
            self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def get_driver(self):
        return self.driver

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def query(self, query, parameters=None, db=None):
        assert self.driver is not None, "Driver not initialized!"
        session = None
        response = None
        try: 
            session = self.driver.session(database=db) if db else self.driver.session() 
            response = list(session.run(query, parameters))
        except Exception as e: 
            print("Query failed:", e)
        finally: 
            if session: 
                session.close()
        return response

def get_db_connection():
    return Neo4jConnection()
