import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.extraction.extraction_agent import extract_invoice_data

def test_extraction_basic():
    # Test with a mock image path that triggers "Emm Vee Traders" logic
    data = extract_invoice_data("path/to/emm_vee_invoice.jpg")
    
    print("Extracted Data:", data)
    
    assert data["Supplier_Name"] == "Detected Supplier"
    assert data["Invoice_No"] == "INV-MOCK"
    assert isinstance(data["Line_Items"], list)
    assert len(data["Line_Items"]) == 1
    
    item1 = data["Line_Items"][0]
    assert item1["Original_Product_Description"] == "Dolo 650mg Tablet"
    assert item1["Stated_Net_Amount"] == 250.0


if __name__ == "__main__":
    test_extraction_basic()
