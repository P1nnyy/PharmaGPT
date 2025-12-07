import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import RawLineItem
from src.normalization import calculate_cost_price

class TestNormalization(unittest.TestCase):
    
    def test_emm_vee_traders_logic(self):
        """Test Rate/Doz conversion for Emm Vee Traders"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1, # Non-zero
            Batch_No="B1",
            Raw_Rate_Column_1="120.00", # 120 per dozen
            Stated_Net_Amount="10.00"
        )
        # Expected: 120 / 12 = 10.0
        cp = calculate_cost_price(item, "Emm Vee Traders")
        self.assertAlmostEqual(cp, 10.0)

    def test_standard_supplier_logic(self):
        """Test standard rate logic for other suppliers"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1,
            Batch_No="B1",
            Raw_Rate_Column_1="100.00", # 100 per unit
            Stated_Net_Amount="100.00"
        )
        # Expected: 100.0
        cp = calculate_cost_price(item, "Jeevan Medicos")
        self.assertAlmostEqual(cp, 100.0)
        
    def test_zero_quantity_logic(self):
        """Test zero quantity handling"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=0, # Zero qty
            Batch_No="B1",
            Raw_Rate_Column_1="100.00",
            Stated_Net_Amount="0.00"
        )
        # Expected: 0.0
        cp = calculate_cost_price(item, "Emm Vee Traders")
        self.assertEqual(cp, 0.0)
        
    def test_string_parsing_resilience(self):
        """Test resilience to string formats in rate"""
        item = RawLineItem(
            Original_Product_Description="Test Item",
            Raw_Quantity=1,
            Batch_No="B1",
            Raw_Rate_Column_1="Rs. 240.00 ", # Currency symbol
            Stated_Net_Amount="20.00"
        )
        # Emm Vee: 240 / 12 = 20
        cp = calculate_cost_price(item, "Emm Vee Traders")
        self.assertAlmostEqual(cp, 20.0)

if __name__ == '__main__':
    unittest.main()
