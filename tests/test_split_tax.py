import os
import sys
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import RawLineItem
from src.normalization import get_effective_tax_rate, calculate_financials

class TestSplitTaxAndTriangulation(unittest.TestCase):

    def test_split_tax_summation(self):
        """Verify CGST + SGST are correctly summed into effective tax rate."""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=10,
            Stated_Net_Amount=105.0,
            Raw_CGST_Percentage="2.5",
            Raw_SGST_Percentage=2.5
        )
        rate = get_effective_tax_rate(item)
        self.assertEqual(rate, 5.0, "Effective tax rate should be 2.5 + 2.5 = 5.0")

    def test_explicit_gst_priority(self):
        """Verify Raw_GST_Percentage takes priority over split taxes."""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=10,
            Stated_Net_Amount=112.0,
            Raw_GST_Percentage=12.0,
            Raw_CGST_Percentage=6.0, # Should be ignored
            Raw_SGST_Percentage=6.0  # Should be ignored
        )
        rate = get_effective_tax_rate(item)
        self.assertEqual(rate, 12.0, "Explicit GST should take priority.")

    def test_triangulation_correction(self):
        """
        Verify Triangulation Logic:
        Scenario: 
          - Quantity: 10
          - Rate: 100
          - Discount: 0
          - Tax: 18%
          - True Net: 1180
          - Mistake: Extractor put 1000 (Taxable) into Stated_Net_Amount
        
        Logic should detect Stated(1000) ~= Taxable(1000) and Override with Calc(1180).
        """
        item = RawLineItem(
            Original_Product_Description="Triangulation Test",
            Raw_Quantity=10,
            Raw_Rate_Column_1=100.0,
            Raw_GST_Percentage=18.0,
            Stated_Net_Amount=1000.0, # WRONG: This is taxable value
            Raw_Taxable_Value=1000.0
        )
        
        result = calculate_financials(item, "Test Supplier")
        
        # Expect Net_Line_Amount to be corrected to 1180.0
        self.assertEqual(result["Net_Line_Amount"], 1180.0, "Triangulation should have corrected the Net Amount to 1180.0")
        self.assertEqual(result["Calculated_Taxable_Value"], 1000.0)

    def test_no_correction_needed(self):
        """Verify correct data is NOT modified."""
        item = RawLineItem(
            Original_Product_Description="Correct Item",
            Raw_Quantity=10,
            Raw_Rate_Column_1=100.0,
            Raw_GST_Percentage=18.0,
            Stated_Net_Amount=1180.0, # CORRECT
            Raw_Taxable_Value=1000.0
        )
        
        result = calculate_financials(item, "Test Supplier")
        
        self.assertEqual(result["Net_Line_Amount"], 1180.0)

if __name__ == '__main__':
    unittest.main()
