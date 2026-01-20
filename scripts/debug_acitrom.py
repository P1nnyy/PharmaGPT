
import os
import sys

sys.path.append(os.getcwd())

from src.services.database import get_db_driver

PRODUCT_NAME = "ACITROM-2MG-30TABS"

def debug_product():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    with driver.session() as session:
        # 1. Inspect GlobalProduct Node
        print(f"--- GlobalProduct: {PRODUCT_NAME} ---")
        gp_query = "MATCH (gp:GlobalProduct {name: $name}) RETURN gp"
        gp_result = session.run(gp_query, name=PRODUCT_NAME).single()
        if gp_result:
            print(dict(gp_result["gp"]))
        else:
            print("❌ GlobalProduct NOT FOUND")

        # 2. Inspect Linked Line Items (History Source)
        print(f"\n--- Linked Line Items (via :IS_VARIANT_OF) ---")
        hist_query = """
        MATCH (l:Line_Item)-[:IS_VARIANT_OF]->(gp:GlobalProduct {name: $name})
        RETURN l.pack_size, l.net_amount, l.hsn_code
        LIMIT 5
        """
        hist_result = session.run(hist_query, name=PRODUCT_NAME)
        count = 0
        for record in hist_result:
            print(record.data())
            count += 1
        if count == 0:
            print("❌ No linked Line Items found.")

        # 3. Search for potential unlinked Line Items (Name Mismatch?)
        print(f"\n--- Potential Unlinked Line Items (Fuzzy Search) ---")
        fuzzy_query = """
        MATCH (l:Line_Item)
        WHERE l.raw_description CONTAINS 'ACITROM' OR l.product_name CONTAINS 'ACITROM'
        RETURN l.raw_description, l.product_name, l.hsn_code
        LIMIT 5
        """
        fuzzy_result = session.run(fuzzy_query)
        for record in fuzzy_result:
            print(record.data())

if __name__ == "__main__":
    debug_product()
