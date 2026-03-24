import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

def count_rels():
    print(f"Connecting to {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
            print("Relationships in DB:")
            for record in result:
                print(f"- {record['type']}: {record['count']}")
        driver.close()
    except Exception as e:
        print(f"Failed to count relationships: {e}")

if __name__ == "__main__":
    count_rels()
