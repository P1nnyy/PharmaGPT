
import sys
import os
sys.path.append(os.getcwd())

from src.database.connection import get_driver, init_driver, close_driver

def check_keys():
    init_driver()
    driver = get_driver()
    if not driver:
        print("No driver")
        return

    query = """
    MATCH (l:Line_Item)
    RETURN l
    LIMIT 1
    """
    
    with driver.session() as session:
        result = session.run(query).single()
        if result:
            node = result["l"]
            print("Keys found in DB:", list(node.keys()))
            print("Sample Data:", dict(node))
        else:
            print("No line items found in DB")

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
        check_keys()
    except Exception as e:
        print(f"Error: {e}")
