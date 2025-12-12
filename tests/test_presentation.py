import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.presentation import format_invoice_for_display

class TestPresentation(unittest.TestCase):
    
    def test_format_display(self):
        """Test formatting of normalized items into display rows"""
        normalized_items = [
            {
                "Standard_Item_Name": "Product A",
                "Pack_Size_Description": "10 strips",
                "Standard_Quantity": 5.0,
                "Calculated_Cost_Price_Per_Unit": 12.50,
                "Discount_Amount_Currency": 2.50,
                "Net_Line_Amount": 100.00,
                "Raw_GST_Percentage": 12,
                "HSN_Code": "3004"
            },
            {
                "Standard_Item_Name": "Product B",
                "Pack_Size_Description": "1x1",
                "Standard_Quantity": 10,
                "Calculated_Cost_Price_Per_Unit": 1000.00,
                "Discount_Amount_Currency": 0.0,
                "Net_Line_Amount": 10000.00,
                "Raw_GST_Percentage": 18 
            }
        ]
        
        display = format_invoice_for_display(normalized_items)
        
        self.assertEqual(len(display), 2)
        
        # Check Row 1
        row1 = display[0]
        self.assertEqual(row1["Sr No."], "1")
        self.assertEqual(row1["HSN Code"], "3004")
        self.assertEqual(row1["Item Name"], "Product A")
        self.assertEqual(row1["Cost Price (Per Unit)"], "₹ 12.50")
        self.assertEqual(row1["Discount (₹)"], "₹ 2.50")
        self.assertEqual(row1["Tax Rate (%)"], "12%")
        
        # Check Row 2
        row2 = display[1]
        self.assertEqual(row2["Sr No."], "2")
        self.assertEqual(row2["Cost Price (Per Unit)"], "₹ 1,000.00") # Check comma formatting
        self.assertEqual(row2["Net Amount (Line Total)"], "₹ 10,000.00")

if __name__ == '__main__':
    unittest.main()
