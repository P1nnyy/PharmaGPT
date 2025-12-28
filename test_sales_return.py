
import logging
from src.workflow.nodes.auditor import audit_extraction

# Mock Data
# Total Purchase = 794.98
# Return = 37.14
# Expected Net = 757.84

def test_sales_return_auditor():
    line_items = [
        {"Product": "Item 1", "Amount": 385.35, "is_sales_return": False},
        {"Product": "Item 2", "Amount": 48.57, "is_sales_return": False},
        {"Product": "Item 3", "Amount": 158.55, "is_sales_return": False},
        {"Product": "Item 4", "Amount": 202.51, "is_sales_return": False},
        {"Product": "Item 5 (Return)", "Amount": 37.14, "is_sales_return": True} # This should be removed
    ]
    
    state = {
        "image_path": "dummy.jpg",
        "line_item_fragments": line_items,
        "global_modifiers": {"Global_Discount_Amount": 0.0},
        "raw_text_rows": ["row1", "row2"]
    }
    
    print("--- START STATE ---")
    print(f"Items: {len(line_items)}")
    
    result = audit_extraction(state)
    
    new_items = result.get("line_items", [])
    new_mods = result.get("global_modifiers", {})
    
    print("\n--- AUDITOR RESULT ---")
    print(f"New Item Count: {len(new_items)}")
    print(f"Global Discount: {new_mods.get('Global_Discount_Amount')}")
    
    item_names = [i["Product"] for i in new_items]
    print(f"Remaining Items: {item_names}")
    
    if len(new_items) == 4 and "Item 5 (Return)" not in item_names:
        print("SUCCESS: Return item removed.")
    else:
        print("FAIL: Return item NOT removed.")
        
    if abs(new_mods.get("Global_Discount_Amount", 0) - 37.14) < 0.1:
        print("SUCCESS: Discount updated cleanly.")
    else:
        print(f"FAIL: Discount mismatch. Got {new_mods.get('Global_Discount_Amount')}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_sales_return_auditor()
