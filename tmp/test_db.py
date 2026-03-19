import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.database import get_db_driver

def test():
    driver = get_db_driver()
    with driver.session() as session:
        res = session.run("MATCH (i:Invoice) RETURN i.invoice_number, i.supplier_name LIMIT 5")
        for r in res:
            print(r)
        
        res = session.run("MATCH (l:Line_Item) RETURN count(l)")
        print(f"Total Line Items: {res.single()[0]}")

if __name__ == "__main__":
    test()
