import sys
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.server import app

client = TestClient(app)

def test_process_invoice_mocked():
    """
    Test the process_invoice endpoint with mocked Neo4j driver.
    """
    # Mock ingest_invoice and driver
    with patch("src.api.server.ingest_invoice") as mock_ingest:
        with patch("src.api.server.driver") as mock_driver:
            # Setup mock driver session
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = mock_session
            
            payload = {
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
            
            response = client.post("/process-invoice", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["normalized_data"][0]["Standard_Item_Name"] == "Dolo 650mg Tablet"
            
            mock_ingest.assert_called_once()

def test_report_endpoint_mocked():
    """
    Test the report endpoint with mocked DB.
    """
    with patch("src.api.server.driver") as mock_driver:
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Mock result for cypher query
        mock_result = {
            "i": {"invoice_number": "INV-123", "supplier_name": "Test Supplier", "grand_total": 1000.0},
            "items": []
        }
        mock_session.run.return_value.single.return_value = mock_result
        
        response = client.get("/report/INV-123")
        assert response.status_code == 200
        assert "Clean Invoice Report" in response.text
        assert "INV-123" in response.text
