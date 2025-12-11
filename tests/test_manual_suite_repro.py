import sys
import os
import unittest
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import RawLineItem
from src.normalization import normalize_line_item, calculate_cost_price

class TestManualSuiteRepro(unittest.TestCase):
    
    def test_emm_vee_rate_priority(self):
        """
        Test Invoice #4 (Emm Vee): 
        Should verify that if Rate/Doz is captured (simulated here as Raw_Rate_Column_1),
        the cost price calculation divides by 12.
        """
        # User goal: "calculated price should be based on Rate/Doz (approx 140.87), not MRP."
        # Let's assume Rate/Doz is 1690.44 (approx 140.87 * 12).
        rate_doz = 1690.44
        mrp = 200.00
        
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1, 
            Batch_No="B1",
            Raw_Rate_Column_1=str(rate_doz), # Extraction maps Rate/Doz here due to yaml priority
            Raw_Rate_Column_2=str(mrp),      # Extraction maps MRP here
            Stated_Net_Amount="100.00"
        )
        
        # Validation: Verify calculate_cost_price divides by 12 for "Emm Vee Traders"
        cp = calculate_cost_price(item, "Emm Vee Traders")
        expected_cp = rate_doz / 12.0
        print(f"\n[Test Emm Vee] Rate/Doz: {rate_doz}, MRP: {mrp}")
        print(f"Calculated CP: {cp}, Expected CP (Rate/Doz / 12): {expected_cp}")
        
        self.assertAlmostEqual(cp, expected_cp, places=2)
        self.assertNotAlmostEqual(cp, mrp) # Ensure it didn't pick MRP

    def test_batch_number_cleaning(self):
        """
        Test Invoice #5 (Sood Medicine):
        Batch Number should no longer contain "OTSI" or "MICR".
        Also check null handling.
        """
        scenarios = [
            ("OTSI 12345", "12345"),
            ("MICR 56789", "56789"),
            ("MHN- BATCH01", "BATCH01"),
            ("215 | BATCH02", "BATCH02"),
            (None, "UNKNOWN"),
            ("   ", "UNKNOWN"),
            ("Valid Batch", "Valid Batch")
        ]
        
        print("\n[Test Batch Cleaning]")
        for raw_batch, expected_batch in scenarios:
            item = RawLineItem(
                Original_Product_Description="Test Item",
                Raw_Quantity=1, 
                Batch_No=raw_batch,
                Stated_Net_Amount="100.00"
            )
            
            result = normalize_line_item(item, "Sood Medicine")
            cleaned_batch = result["Batch_No"]
            print(f"Input: '{raw_batch}' -> Output: '{cleaned_batch}'")
            self.assertEqual(cleaned_batch, expected_batch)

if __name__ == '__main__':
    unittest.main()
