import pytest
from src.workflow.nodes.auditor import audit_extraction
from src.workflow.state import InvoiceState

def test_auditor_swapped_quantity_correction():
    # Scenario: 
    # Item A: Rate 100, Amount 500. Extracted Qty = 2. (Should be 5)
    # Item B: Rate 50, Amount 100. Extracted Qty = 5. (Should be 2)
    
    # Math:
    # Item A: 100 * 2 = 200 != 500. (Discrepancy)
    # Item B: 50 * 5 = 250 != 100. (Discrepancy)
    
    # Swap Hypothesis:
    # Item A Qty 5 -> 100 * 5 = 500 (Match!)
    # Item B Qty 2 -> 50 * 2 = 100 (Match!)
    
    state = {
        "image_path": "dummy.jpg",
        "raw_text_rows": ["..."],
        "line_item_fragments": [
            {
                "Product": "Item A",
                "Rate": 100.0,
                "Amount": 500.0,
                "Qty": 2.0, # WRONG (Swapped)
            },
            {
                "Product": "Item B",
                "Rate": 50.0,
                "Amount": 100.0,
                "Qty": 5.0, # WRONG (Swapped)
            }
        ],
        "global_modifiers": {}
    }

    # Run Auditor (after we implement the fix)
    result = audit_extraction(state)
    items = result["line_items"]
    
    # Verify Item A
    item_a = next(i for i in items if i["Product"] == "Item A")
    assert item_a["Qty"] == 5.0, f"Expected Qty 5 for Item A, got {item_a['Qty']}"
    
    # Verify Item B
    item_b = next(i for i in items if i["Product"] == "Item B")
    assert item_b["Qty"] == 2.0, f"Expected Qty 2 for Item B, got {item_b['Qty']}"

if __name__ == "__main__":
    try:
        test_auditor_swapped_quantity_correction()
        print("Test PASSED: Swapped Quantities were auto-corrected.")
    except Exception as e:
        print(f"Test FAILED: {e}")
