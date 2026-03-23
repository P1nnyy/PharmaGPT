import json
from src.services.database import get_db_driver

driver = get_db_driver()
query = "MATCH (i:Invoice) WHERE i.status IN ['DRAFT', 'PROCESSING', 'ERROR'] RETURN i.raw_state as state, i.invoice_id as id"
with driver.session() as session:
    results = session.run(query)
    for record in results:
        state = record["state"]
        if state:
            d = json.loads(state)
            items = d.get('normalized_items', [])
            print(f"ID: {record['id']} - Items: {len(items)} - Has Nulls: {any(x is None for x in items)}")
            if any(x is None for x in items):
                print(items)
