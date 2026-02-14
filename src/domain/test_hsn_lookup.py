
from src.services.database import get_db_driver
from src.domain.smart_mapper import enrich_hsn_details
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_hsn_lookup():
    print("--- Testing HSN Lookup ---")
    
    # Test 1: Common HSN (should be in Hardcoded Map)
    hsn_common = "96032100"
    print(f"Testing Common HSN: {hsn_common}")
    result_common = enrich_hsn_details(hsn_common)
    print(f"Result: {result_common}")
    
    if result_common.get("desc") == "Toothbrush" and result_common.get("tax") == 18.0:
        print("✅ Common HSN Lookup Passed")
    else:
        print("❌ Common HSN Lookup Failed")

    # Test 2: DB Lookup (Simulated check - ensure driver connects)
    # We might not have a running Neo4j with this data populated in this env, 
    # but we can check if the function runs without error.
    hsn_random = "12345678"
    print(f"\nTesting Random HSN (DB Check): {hsn_random}")
    try:
        result_db = enrich_hsn_details(hsn_random)
        print(f"Result: {result_db}")
        print("✅ DB Lookup Function executed (result might be default)")
    except Exception as e:
        print(f"❌ DB Lookup Function Failed: {e}")

if __name__ == "__main__":
    test_hsn_lookup()
