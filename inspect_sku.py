
from src.services.database import get_db_driver
import sys

def check_product(name):
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    query = """
    MATCH (p:GlobalProduct {name: $name})
    RETURN p
    """
    with driver.session() as session:
        result = session.run(query, name=name).single()
        if result:
            print(f"Product Found: {name}")
            node = result["p"]
            print(dict(node))
        else:
            print(f"Product NOT Found: {name}")

if __name__ == "__main__":
    check_product("ONDERO MET 2.5/1000 M")
