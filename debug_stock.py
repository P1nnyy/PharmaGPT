from shop_manager import PharmaShop

shop = PharmaShop()

print("--- Debugging TestDrug ---")
query = """
MATCH (p:Product {name: "TestDrug"})<-[:IS_BATCH_OF]-(b:InventoryBatch)
RETURN p.name, p.pack_size, b.batch_number, b.sealed_packs, b.loose_tablets, b.current_stock
"""

with shop.driver.session() as session:
    result = session.run(query)
    for record in result:
        print(record.data())

print("\n--- Testing Sell Item Query Logic ---")
test_query = """
MATCH (p:Product {name: "TestDrug"})<-[:IS_BATCH_OF]-(b:InventoryBatch)
RETURN (coalesce(b.sealed_packs, 0) * coalesce(p.pack_size, 1)) + coalesce(b.loose_tablets, 0) as calculated_stock
"""
with shop.driver.session() as session:
    result = session.run(test_query)
    for record in result:
        print(record.data())

shop.close()
