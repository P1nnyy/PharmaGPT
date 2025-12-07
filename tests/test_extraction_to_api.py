import sys
import os
import httpx
import pytest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.extraction.extraction_agent import extract_invoice_data
from src.api.server import app

def test_extraction_to_api_flow():
    """
    Integration test: Extraction -> Validation -> API -> Processing -> Response.
    """
    # 1. Run Extraction
    # Uses internal mock OCR for "emm_vee" logic
    image_path = "path/to/emm_vee_invoice.jpg" 
    extracted_data = extract_invoice_data(image_path)
    
    assert extracted_data is not None
    print("\n[+] Extraction Successful.")
    
    # 2. Send to API
    # Using TestClient to simulate "live" API call without needing background uvicorn process
    # The prompt asked "using the httpx library". TestClient USES httpx under the hood.
    
    # MOCK DATABASE: The server returns 503 if 'driver' is None.
    # Since we are not running a real Neo4j instance in this environment, we must mock it within the app instance.
    from unittest.mock import MagicMock
    from src.api.server import driver
    
    # Patch the driver in the server module
    # We need to simulate a session and successful write
    with MagicMock() as mock_driver:
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Inject mock driver into app state or global variable in server.py
        # Since server.py uses a global 'driver' variable, we need to patch it.
        import src.api.server
        src.api.server.driver = mock_driver
        
        client = TestClient(app)
        response = client.post("/process-invoice", json=extracted_data)
        
        # 3. Assertions
        if response.status_code != 200:
            print(f"API Error: {response.text}")
        
        assert response.status_code == 200
        
        result = response.json()
        assert result["status"] == "success"

    
    # Check normalized data in response
    normalized_items = result["normalized_data"]
    assert len(normalized_items) == 2
    
    # Verify standardization worked (Extraction got "Dolo 650", Normalization should make it "Dolo 650mg Tablet")
    item1 = normalized_items[0]
    print(f"[+] Standardization Check: {item1['Standard_Item_Name']}")
    
    assert item1["Standard_Item_Name"] == "Dolo 650mg Tablet"
    
    print("[+] Integration Test Passed!")

if __name__ == "__main__":
    # If running as script
    test_extraction_to_api_flow()
