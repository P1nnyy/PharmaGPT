import sys
import os
import json
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv() # Load env vars BEFORE imports that rely on them

from src.workflow.nodes.mapper import execute_mapping

# Mock State
MOCK_STATE = {
    "raw_text_rows": ["Acitrom 2mg 10s Tab 12345 10/25 3004 15.50 155.00 19.99"],
    "global_modifiers": {"Supplier_Name": "Test Pharma"}
}

# Mock LLM Response to ensure deterministic "Product" extraction
MOCK_LLM_RESPONSE = """
```json
{
    "line_items": [
        {
            "Product": "Para-500-Tab", 
            "Qty": 10.0,
            "Amount": 155.0
        }
    ]
}
```
"""

@patch('src.workflow.nodes.mapper.genai.GenerativeModel')
def test_smart_mapper(mock_model_cls):
    print("Testing Smart Mapper Logic...")
    
    # Mock LLM
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = MOCK_LLM_RESPONSE
    mock_model_cls.return_value = mock_model
    
    # We rely on the REAL Neo4j DB for alias lookup (integration test)
    # Ensure Alias "Para-500-Tab" -> "Paracetamol-500" exists (from previous test)
    
    try:
        from src.services.database import connect_db
        connect_db() # Init DB connection config if needed
        
        result = execute_mapping(MOCK_STATE)
        
        items = result.get("line_item_fragments", [])
        if not items:
            print("FAILURE: No items mapped.")
            return

        item = items[0]
        print(f"Mapped Item: {item}")
        
        # Check if Standard_Item_Name was injected
        if item.get("Standard_Item_Name") == "Paracetamol-500":
            print("SUCCESS: Smart Mapper resolved Alias 'Para-500-Tab' -> 'Paracetamol-500'")
        else:
            print(f"FAILURE: Expected 'Paracetamol-500', got {item.get('Standard_Item_Name')}")
            
    except Exception as e:
        print(f"TEST FAILED with Error: {e}")

if __name__ == "__main__":
    test_smart_mapper()
