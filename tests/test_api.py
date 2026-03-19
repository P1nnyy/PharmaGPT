import sys
import os
import unittest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.server import app
from src.api.routes.auth import get_current_user_email
# Override auth dependency for tests
async def mock_get_current_user():
    return "test@example.com"

app.dependency_overrides[get_current_user_email] = mock_get_current_user

client = TestClient(app)

class TestAPI(unittest.TestCase):

    def test_process_invoice_mocked(self):
        """
        Test the process_invoice endpoint with mocked Neo4j driver.
        """
        # Mock ingest_invoice, driver, AND extract_invoice_data
        # Mock ingest_invoice, driver, AND process_invoice_background
        with patch("src.api.routes.invoices.ingest_invoice") as mock_ingest, \
             patch("src.api.routes.invoices.get_db_driver") as mock_driver, \
             patch("src.api.routes.invoices.process_invoice_background") as mock_extract:
            
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
                "/invoices/batch-upload", 
                files={"files": ("test.jpg", b"fake_content", "image/jpeg")}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            # Batch upload returns a list of results
            self.assertEqual(data[0]["status"], "processing")
            
            mock_extract.assert_called_once()

    def test_report_endpoint_mocked(self):
        """
        Test the report endpoint with mocked DB.
        """
        with patch("src.api.routes.reporting.get_db_driver") as mock_get_driver:
            mock_driver = MagicMock()
            mock_get_driver.return_value = mock_driver
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = mock_session
            
            # Use a mock record that supports .get() and indexing
            mock_result = MagicMock()
            mock_result.__getitem__.side_effect = lambda k: {
                "i": {"invoice_number": "INV-123", "supplier_name": "Test Supplier", "grand_total": 1000.0, "invoice_date": "2024-01-01"},
                "items": []
            }[k]
            
            mock_session.run.return_value.single.return_value = mock_result
            
            response = client.get("/report/INV-123")
            self.assertEqual(response.status_code, 200)
            self.assertIn("INV-123", response.text)

if __name__ == "__main__":
    unittest.main()
