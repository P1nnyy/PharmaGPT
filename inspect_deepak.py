import sys
import os
sys.path.append(os.getcwd())
try:
    from src.api.server import get_db_driver
except ImportError:
    from src.domain.persistence import get_db_driver
import json

def inspect_extraction():
    driver = get_db_driver()
    # Search for invoice by semi-fuzzy filename match
    query = """
    MATCH (i:Invoice)
    WHERE toLower(i.filename) CONTAINS 'deepak'
    RETURN i.filename, i.raw_state, i.status, i.error_message, i.created_at, i.is_duplicate, i.duplicate_warning
    ORDER BY i.created_at DESC
    LIMIT 5
    """
    with driver.session() as session:
        result = session.run(query)
        
        print(f"{'Time':<20} | {'Status':<10} | {'IsDup':<5} | {'Error/Warning'}")
        print("-" * 100)
        
        for record in result:
             created = record['i.created_at']
             status = record['i.status']
             is_dup = record.get('i.is_duplicate', False)
             msg = record['i.error_message'] or record.get('i.duplicate_warning') or ""
             raw_state = record['i.raw_state']
             print(f"{str(created):<20} | {status:<10} | {str(is_dup):<5} | {msg}")
             if raw_state:
                 import json
                 try:
                    js = json.loads(raw_state)
                    print(json.dumps(js.get("invoice_data", {}), indent=2))
                 except:
                    print("Raw State not JSON")
             print("-" * 50)

if __name__ == "__main__":
    inspect_extraction()
