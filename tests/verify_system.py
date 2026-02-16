
import sys
import os
import unittest
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

load_dotenv()

from src.domain.normalization.financials import parse_quantity
from src.services.database import get_db_driver

class TestSystemFixes(unittest.TestCase):
    
    def test_tc01_scheme_loop_fix(self):
        """TC-01: Verify '2.75+.250' parses correctly to 3.0"""
        s = "2.75+.250"
        qty = parse_quantity(s)
        print(f"\n[TC-01] Parsing '{s}' -> {qty}")
        self.assertEqual(qty, 3, "Failed to parse .250 correctly (Scheme Loop Fix)")
        
    def test_tc04_persistence_schema(self):
        """TC-04: Verify DB accepts and returns 'pack_size_primary'"""
        driver = get_db_driver()
        if not driver:
            print("\n[TC-04] Skip: No DB Driver")
            return

        with driver.session() as session:
            # 1. Create Dummy
            session.run("MERGE (gp:GlobalProduct {name: '_TEST_SYS_VERIFY_'})")
            
            # 2. Update with New Fields (Simulating fix_enrichment.py)
            update_query = """
            MATCH (gp:GlobalProduct {name: '_TEST_SYS_VERIFY_'})
            SET gp.pack_size_primary = 15,
                gp.pack_size_secondary = 5,
                gp.is_enriched = true,
                gp.manufacturer = 'Test Pharma'
            RETURN gp.pack_size_primary as p1, gp.manufacturer as mfr
            """
            result = session.run(update_query).single()
            
            print(f"\n[TC-04] persistence check: {result['p1']}, {result['mfr']}")
            
            self.assertEqual(result['p1'], 15)
            self.assertEqual(result['mfr'], 'Test Pharma')
            
            # 3. Cleanup
            session.run("MATCH (gp:GlobalProduct {name: '_TEST_SYS_VERIFY_'}) DELETE gp")

if __name__ == '__main__':
    unittest.main()
