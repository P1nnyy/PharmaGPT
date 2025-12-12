import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import InvoiceExtraction, RawLineItem
from src.persistence import ingest_invoice

class TestPersistence(unittest.TestCase):
    
    def test_ingest_invoice_calls(self):
        """Test that ingest_invoice calls driver methods with correct queries"""
        
        # 1. Setup Mock Driver
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()
        
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Mock execute_write to just call the function passed to it
        def side_effect(func, *args, **kwargs):
            return func(mock_tx, *args, **kwargs)
        
        mock_session.execute_write.side_effect = side_effect
        
        # 2. Prepare Data
        invoice_data = InvoiceExtraction(
            Supplier_Name="Test Supplier",
            Invoice_No="INV-001",
            Invoice_Date="2024-01-01",
            Line_Items=[RawLineItem(
                Original_Product_Description="Test Product",
                Raw_Quantity="5",
                Stated_Net_Amount="52.5",
                Batch_No="B1" 
            )]
        )
        normalized_items = [
            {
                "Standard_Item_Name": "Product A",
                "Pack_Size_Description": "10s",
                "Standard_Quantity": 5.0,
                "Calculated_Cost_Price_Per_Unit": 10.0,
                "Discount_Amount_Currency": 0.0,
                "Calculated_Taxable_Value": 50.0,
                "Net_Line_Amount": 52.5,  # Grand total = 52.5
                "Raw_GST_Percentage": 5
            }
        ]
        
        # 3. Call Ingest
        ingest_invoice(mock_driver, invoice_data, normalized_items)
        
        # 4. Verify Driver Calls
        # Check transaction calls
        # We expect 2 writes: 1 for invoice, 1 for line item
        self.assertEqual(mock_session.execute_write.call_count, 2)
        
        # Verify Invoice Query
        # We can't easily inspect the exact query string matching due to whitespace, 
        # but we can check if tx.run was called with expected params.
        
        # Get all calls to tx.run
        run_calls = mock_tx.run.call_args_list
        self.assertEqual(len(run_calls), 2)
        
        # Check first call (Invoice) args
        invoice_call_kwargs = run_calls[0].kwargs
        self.assertEqual(invoice_call_kwargs['invoice_no'], "INV-001")
        self.assertEqual(invoice_call_kwargs['grand_total'], 52.5)
        
        # Check second call (Line Item) args
        item_call_kwargs = run_calls[1].kwargs
        self.assertEqual(item_call_kwargs['standard_item_name'], "Product A")
        self.assertEqual(item_call_kwargs['net_amount'], 52.5)

if __name__ == '__main__':
    unittest.main()
