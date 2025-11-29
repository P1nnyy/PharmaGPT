import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from streamlit.testing.v1 import AppTest
import pandas as pd
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the dependencies before they are imported by app.py
sys.modules["shop_manager"] = MagicMock()
sys.modules["agent"] = MagicMock()
sys.modules["vision_agent"] = MagicMock()

# Setup the mocks
mock_shop = MagicMock()
sys.modules["shop_manager"].PharmaShop.return_value = mock_shop

# Mock run_agent
mock_run_agent = MagicMock(return_value="I am a mocked agent response.")
sys.modules["agent"].run_agent = mock_run_agent

class TestAppFull(unittest.TestCase):
    def setUp(self):
        os.environ["GOOGLE_API_KEY"] = "fake_key"
        
        # Reset mocks
        mock_shop.reset_mock()
        mock_shop.get_product_names.return_value = ["Dolo 650", "Augmentin"]
        mock_shop.check_inventory.return_value = [
            {
                "product_name": "Dolo 650", 
                "batch_number": "B123", 
                "expiry_date": date(2025, 12, 31),
                "quantity_packs": 10,
                "quantity_loose": 0,
                "pack_size": 15,
                "mrp": 30.0,
                "manufacturer": "Micro Labs",
                "dosage_form": "Tablet",
                "stock_display": "10 Packs"
            }
        ]
        mock_shop.sell_item.return_value = {
            "status": "success", "tax": 5.0, "details": "Sold from B123"
        }
        mock_shop.add_medicine_stock.return_value = "✅ Added 10 Sealed Packs"

    def test_chat_interface(self):
        """Test Chat Interface (Agent)"""
        at = AppTest.from_file("app.py")
        at.run()
        
        # Check if chat input exists
        if len(at.chat_input) == 0:
            self.fail("Chat input not found in the app.")
            
        at.chat_input[0].set_value("Hello").run()
        
        # Check for user message and assistant response
        # We expect 2 messages: User "Hello" and Assistant "I am a mocked agent response."
        self.assertEqual(len(at.chat_message), 2)
        self.assertEqual(at.chat_message[0].markdown[0].value, "Hello")
        self.assertEqual(at.chat_message[1].markdown[0].value, "I am a mocked agent response.")

    def test_inventory_display(self):
        """Test Inventory Display (Expander)"""
        at = AppTest.from_file("app.py")
        at.run()
        
        # Verify check_inventory was called
        mock_shop.check_inventory.assert_called()
        
        # Check if dataframe is present
        # It might be inside an expander, but AppTest should list it in at.dataframe
        if len(at.dataframe) == 0:
            # If dataframe is not found, maybe the expander is closed or data is empty?
            # Mock returns data, so it should be there.
            # Let's check if we can find the expander.
            pass
        
        self.assertTrue(len(at.dataframe) > 0, "No dataframe found")
        
        # Check content of the first dataframe
        df = at.dataframe[0].value
        # The dataframe in app.py shows batches.
        # Columns: Batch #, Expiry, Stock Status, MRP
        # app.py renames columns: "batch_number" -> "Batch #"
        self.assertIn("Batch #", df.columns)
        self.assertEqual(len(df), 1) # 1 batch in mock

    def test_ingestion_toggle(self):
        """Test 'Scan Bill' button toggles ingestion view"""
        at = AppTest.from_file("app.py")
        at.run()
        
        # Initial state: show_ingestion is False (default)
        # Find "Scan Bill" button
        scan_btn = None
        for btn in at.button:
            if "Scan Bill" in btn.label:
                scan_btn = btn
                break
        
        if scan_btn:
            scan_btn.click().run()
            # Now ingestion section should be visible
            # Check for "Bill Ingestion" text in markdown
            found_text = False
            for md in at.markdown:
                if "Bill Ingestion" in md.value:
                    found_text = True
                    break
            self.assertTrue(found_text, "Ingestion section not visible after clicking Scan Bill")
        else:
            self.fail("Scan Bill button not found")

if __name__ == "__main__":
    unittest.main()
