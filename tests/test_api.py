import sys
import os
import unittest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.server import app

client = TestClient(app)

class TestAPI(unittest.TestCase):

    def test_process_invoice_mocked(self):
        """
        Test the process_invoice endpoint with mocked Neo4j driver.
        """
        # Mock ingest_invoice, driver, AND extract_invoice_data
        with patch("src.api.server.ingest_invoice") as mock_ingest, \
             patch("src.api.server.driver") as mock_driver, \
             patch("src.api.server.extract_invoice_data") as mock_extract:
            
            # Setup mock driver session
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = mock_session
            
            # Setup mock extraction return
            extracted_data = {
                "Supplier_Name": "Test Supplier",
                "Invoice_No": "INV-123",
                "Invoice_Date": "2024-01-01",
                "Line_Items": [
                    {
                        "Original_Product_Description": "Dolo 650",
                        "Raw_Quantity": "10",
                        "Batch_No": "B1",
                        "Raw_Rate_Column_1": "100",
                        "Stated_Net_Amount": "105"
                    }
                ]
            }
            mock_extract.return_value = extracted_data
            
            # Send file
            response = client.post(
                "/process-invoice", 
                files={"file": ("test.jpg", b"fake_content", "image/jpeg")}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["normalized_data"][0]["Standard_Item_Name"], "Dolo 650mg Tablet")
            
            mock_ingest.assert_called_once()

    def test_report_endpoint_mocked(self):
        """
        Test the report endpoint with mocked DB.
        """
        with patch("src.api.server.driver") as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = mock_session
            
            # Mock result for cypher query
            mock_result = {
                "i": {"invoice_number": "INV-123", "supplier_name": "Test Supplier", "grand_total": 1000.0},
                "items": [
                    {
                        "line": {"calculated_tax_amount": 50.0, "hsn_code": "3004"}, 
                        "product": {"name": "Test Product"},
                        "raw_desc": "Dolo",
                        "stated_net": 1050.0,
                        "batch_no": "B1",
                        "hsn_code": "3004"
                    }
                ]
            }
            mock_session.run.return_value.single.return_value = mock_result
            
            response = client.get("/report/INV-123")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Clean Invoice Report", response.text)
            self.assertIn("INV-123", response.text)
            self.assertIn("3004", response.text)

if __name__ == "__main__":
    unittest.main()
