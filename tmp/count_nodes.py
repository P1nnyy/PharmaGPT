import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.database import get_db_driver

def check():
    driver = get_db_driver()
    with driver.session() as session:
        res = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
        for r in res:
            print(f"{r['labels']}: {r['count']}")

if __name__ == "__main__":
    check()
