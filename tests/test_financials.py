import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import RawLineItem
from src.normalization import calculate_cost_price, calculate_financials

class TestFinancials(unittest.TestCase):
    
    def test_financial_calculation_exact(self):
        """Test exact match financial calculation"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=10,
            Batch_No="B1",
            Raw_Rate_Column_1="100.00", # CP = 100
            Raw_Discount_Percentage="10", # 10%
            Raw_GST_Percentage="5", # 5%
            Stated_Net_Amount="945.00" # Expected net
        )
        # Gross = 10 * 100 = 1000
        # Discount = 1000 * 10% = 100
        # Taxable = 900
        # Tax = 900 * 5% = 45
        # Total = 945
        
        result = calculate_financials(item, "Standard Supplier")
        self.assertEqual(result["Net_Line_Amount"], 945.0)
        self.assertEqual(result["Calculated_Taxable_Value"], 900.0)
        
    def test_reconciliation_within_tolerance(self):
        """Test reconciliation using stated amount when within tolerance"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1,
            Batch_No="B1",
            Raw_Rate_Column_1="100.00",
            Raw_Discount_Percentage="0",
            Raw_GST_Percentage="0",
            Stated_Net_Amount="100.04" # Calculated is 100. Diff 0.04 <= 0.05
        )
        # Calculated = 100.
        
        result = calculate_financials(item, "Standard Supplier")
        # Should adopt stated amount
        self.assertEqual(result["Net_Line_Amount"], 100.04)
        
    def test_reconciliation_outside_tolerance(self):
        """Test reconciliation ignoring stated amount when outside tolerance"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1,
            Batch_No="B1",
            Raw_Rate_Column_1="100.00",
            Raw_Discount_Percentage="0",
            Raw_GST_Percentage="0",
            Stated_Net_Amount="105.00" # Calculated 100. Diff 5.0 > 0.05
        )
        
        result = calculate_financials(item, "Standard Supplier")
        # Should keep calculated amount
        self.assertEqual(result["Net_Line_Amount"], 100.0)

if __name__ == '__main__':
    unittest.main()
