import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

def check_conn():
    print(f"Connecting to {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as n")
            record = result.single()
            print(f"Connection Successful! Result: {record['n']}")
        driver.close()
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    check_conn()
