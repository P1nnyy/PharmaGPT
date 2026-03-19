import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.database import get_db_driver

def debug_db():
    driver = get_db_driver()
    with driver.session() as session:
        print("Labels:")
        res = session.run("CALL db.labels()")
        for r in res:
            print(f" - {r[0]}")
            
        print("\nRelationship Types:")
        res = session.run("CALL db.relationshipTypes()")
        for r in res:
            print(f" - {r[0]}")
            
        print("\nNode Counts:")
        res = session.run("MATCH (n) RETURN labels(n)[0] as label, count(*) as count")
        for r in res:
            print(f" - {r['label']}: {r['count']}")

if __name__ == "__main__":
    debug_db()
