from src.services.database import get_db_driver
import os

def wipe_all_processed():
    driver = get_db_driver()
    if not driver:
        print("Driver fail")
        return
        
    # Hard delete all drafts/duplicates for all users (or targeted query)
    # Since we are debugging locally for this user
    query = """
    MATCH (i:Invoice)
    WHERE i.status IN ['PROCESSING', 'DRAFT', 'ERROR']
    DETACH DELETE i
    """
    with driver.session() as session:
        session.run(query)
    print("Wiped all DRAFT/ERROR/PROCESSING invoices.")

if __name__ == "__main__":
    wipe_all_processed()
