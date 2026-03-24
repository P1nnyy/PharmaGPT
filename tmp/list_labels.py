import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

def list_labels():
    print(f"Connecting to {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("CALL db.labels()")
            print("Labels in DB:")
            for record in result:
                print(f"- {record[0]}")
        driver.close()
    except Exception as e:
        print(f"Failed to list labels: {e}")

if __name__ == "__main__":
    list_labels()
