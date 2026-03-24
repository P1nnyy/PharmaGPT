import sys
import os
import asyncio
import json

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.workflow.nodes.mathematics import apply_correction

async def test_healing():
    print("Testing healing logic in apply_correction node...")
    
    # Simulate a state with missing taxable_value but has line items and sub_total
    state = {
        "line_items": [
            {"Product": "Item A", "Amount": "100.0", "Qty": "1", "SGST_Percent": "6", "CGST_Percent": "6"}
        ],
        "global_modifiers": {
            "sub_total": "100.0",
            "global_discount": "0.0",
            "taxable_value": None,  # Missing/None
            "total_sgst": "6.0",
            "total_cgst": "6.0",
            "round_off": "0.0",
            "Stated_Grand_Total": "112.0"
        },
        "correction_factor": 1.0
    }
    
    result = await apply_correction(state)
    final_output = result.get("final_output", {})
    
    print(f"Healed taxable_value: {final_output.get('taxable_value')}")
    
    if final_output.get("taxable_value") == 100.0:
        print("Success! taxable_value was healed.")
    else:
        print(f"Failed! taxable_value is {final_output.get('taxable_value')}")

if __name__ == "__main__":
    asyncio.run(test_healing())
