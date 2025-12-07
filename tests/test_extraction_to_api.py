import sys
import os
import httpx
import pytest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.extraction.extraction_agent import extract_invoice_data
from src.api.server import app

import sys
import os
import httpx
import pytest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We test the SERVER logic which calls extraction internally.
from src.api.server import app

def test_extraction_to_api_flow():
    """
    Integration test: File Upload -> API -> Extraction (Gemini/Mock) -> Validation -> Processing -> Response.
    """
    # 1. Prepare Dummy Image
    # We create a dummy file to simulate upload. 
    # Use a filename that triggers the "emm_vee" mock fallback logic in case Gemini Key is missing.
    dummy_image_path = "emm_vee_invoice.jpg"
    with open(dummy_image_path, "wb") as f:
        f.write(b"Fake Image Content")
        
    try:
        # 2. Setup Mock Database and Patch Extraction
        from unittest.mock import MagicMock, patch
        
        # Mock Data to define what "Vision" would return
        mock_vision_data = {
            "header": "INVOICE HEADER\nEmm Vee Traders\nLic No: 12345",
            "rows": [
                "Dolo 650     10 strips     Batch001     100.00     1050.00",
                "Augmentin 625   5 strips   Batch002     200.00     1050.00   5%"
            ]
        }

        with MagicMock() as mock_driver, \
             patch('src.extraction.extraction_agent.get_raw_text_from_vision', return_value=mock_vision_data):
            
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = mock_session
            
            # Inject
            import src.api.server
            src.api.server.driver = mock_driver
            
            client = TestClient(app)
            
            # 3. Send File to API
            with open(dummy_image_path, "rb") as f:
                response = client.post(
                    "/process-invoice", 
                    files={"file": ("emm_vee_invoice.jpg", f, "image/jpeg")}
                )
            
            # 4. Assertions
            if response.status_code != 200:
                print(f"API Error: {response.text}")
            
            assert response.status_code == 200
            
            result = response.json()
            assert result["status"] == "success"
            
            # Check normalized data in response
            normalized_items = result.get("normalized_data", [])
            assert len(normalized_items) == 2
            
            item1 = normalized_items[0]
            print(f"[+] Standardization Check: {item1['Standard_Item_Name']}")
            assert item1["Standard_Item_Name"] == "Dolo 650mg Tablet"
            print("[+] Integration Test Passed!")
                 
    finally:
        if os.path.exists(dummy_image_path):
            os.remove(dummy_image_path)

if __name__ == "__main__":
    test_extraction_to_api_flow()

if __name__ == "__main__":
    # If running as script
    test_extraction_to_api_flow()
