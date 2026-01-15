import sys
import os
sys.path.append(os.getcwd())
try:
    from src.api.server import get_db_driver
except ImportError:
    from src.domain.persistence import get_db_driver
import json

def debug_failures():
    driver = get_db_driver()
    query = """
    MATCH (i:Invoice)
    WHERE i.status = 'ERROR'
    RETURN i.filename, i.error_message, i.created_at
    ORDER BY i.created_at DESC
    LIMIT 10
    """
    with driver.session() as session:
        result = session.run(query)
        print(f"{'Filename':<30} | {'Error Message'}")
        print("-" * 80)
        for record in result:
            filename = record["i.filename"] or "Unknown"
            error = record["i.error_message"] or "No message"
            print(f"{filename:<30} | {error}")

if __name__ == "__main__":
    debug_failures()
