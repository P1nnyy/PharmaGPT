
from src.services.database import get_db_driver

try:
    print("Attempting to get DB Driver...")
    driver = get_db_driver()
    if driver:
        print("Driver obtained. verifying connectivity...")
        driver.verify_connectivity()
        print("Connectivity Verified!")
        with driver.session() as session:
            result = session.run("RETURN 1 as val").single()
            print(f"Query Result: {result['val']}")
    else:
        print("Failed to get Driver (None returned)")
except Exception as e:
    print(f"DB Test Failed: {e}")
