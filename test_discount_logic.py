
import logging
from src.workflow.nodes.critic import critique_extraction
from src.workflow.nodes.mathematics import apply_correction
from src.normalization import normalize_line_item

# Mock Data from User Report
# Calculated: 4300.52
# Stated: 4290.00
# Possible Discount: 35.00? (Or just implicit scaling)

def test_pipeline():
    # Setup State
    grand_total = 4290.00
    line_sum = 4300.52
    
    # Create 1 dummy item representing the sum
    lines = [{
        "Product": "Test Item", 
        "Qty": 1, 
        "Rate": 4300.52, 
        "MRP": 5000.0, # Add MRP to pass health check
        "Amount": 4300.52,
        "Stated_Net_Amount": 4300.52
    }]
    
    state = {
        "line_items": lines,
        "line_item_fragments": lines,
        "global_modifiers": {
            "Stated_Grand_Total": grand_total,
            "Global_Discount_Amount": 0.0 # Test assuming Not Extracted
        },
        "anchor_totals": {"Stated_Grand_Total": grand_total}
    }
    
    print(f"--- START STATE ---")
    print(f"Line Sum: {lines[0]['Amount']}")
    print(f"Target Total: {grand_total}")
    
    # 1. Run Critic
    print(f"\n--- RUNNING CRITIC ---")
    critic_result = critique_extraction(state)
    verdict = critic_result["critic_verdict"]
    factor = critic_result.get("correction_factor", 1.0)
    print(f"Critic Verdict: {verdict}")
    print(f"Correction Factor: {factor}")
    
    if verdict not in ["APPLY_MARKUP", "APPLY_MARKDOWN"]:
        print("FAIL: Critic did not request Solver adjustment.")
        return

    # 2. Run Solver
    print(f"\n--- RUNNING SOLVER ---")
    state["correction_factor"] = factor
    solver_result = apply_correction(state)
    solver_lines = solver_result["line_items"]
    
    s_item = solver_lines[0]
    print(f"Solver Output Net Amount: {s_item.get('net_amount')}")
    print(f"Solver Logic Note: {s_item.get('Logic_Note')}")
    
    if abs(s_item.get('net_amount', 0) - grand_total) > 1.0:
         print(f"FAIL: Solver output {s_item.get('net_amount')} does not match Target {grand_total}")
    else:
         print("SUCCESS: Solver adjusted correctly.")

    # 3. Run Normalization
    print(f"\n--- RUNNING NORMALIZATION ---")
    # Simulation of invoices.py loop
    norm_item = normalize_line_item(s_item, "Test Supplier")
    
    print(f"Normalized Net_Line_Amount: {norm_item['Net_Line_Amount']}")
    print(f"Normalized Final_Unit_Cost: {norm_item['Final_Unit_Cost']}")
    
    if abs(norm_item['Net_Line_Amount'] - grand_total) > 1.0:
        print(f"FAIL: Normalization reverted the value! {norm_item['Net_Line_Amount']} != {grand_total}")
    else:
        print("SUCCESS: Normalization preserved the value.")

if __name__ == "__main__":
    # Configure logging to show info
    logging.basicConfig(level=logging.INFO)
    test_pipeline()
