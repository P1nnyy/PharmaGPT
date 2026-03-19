import os
import json
from langfuse import Langfuse
from src.workflow.nodes.mapper import execute_mapping
from src.workflow.state import InvoiceState

# Setup
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
has_langfuse = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

if has_langfuse:
    langfuse = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST
    )
else:
    langfuse = None
    print("DEBUG: Langfuse keys missing. Tracing will be skipped.")

# Debug Environment
print(f"DEBUG: GOOGLE_API_KEY present: {bool(os.getenv('GOOGLE_API_KEY'))}")
print(f"DEBUG: LANGFUSE_PUBLIC_KEY present: {bool(LANGFUSE_PUBLIC_KEY)}")

# Test Data (Gold Standard)
TEST_CASES = [
    {
        "input": "METOLAR XR 50MG 1X15 CAP B.NO: ABC123 EXP: 12/26 QTY: 10 RATE: 100.00 MRP: 148.00",
        "expected": {
            "name": "METOLAR XR 50MG",
            "pack_size": "1X15",
            "batch_no": "ABC123",
            "expiry_date": "12/26",
            "quantity": 10,
            "mrp": 148.00
        }
    },
    {
        "input": "LEVESAM 500 1X10 TAB B.NO: XYZ789 EXP: 05/27 QTY: 5 RATE: 200.00 MRP: 250.00",
        "expected": {
            "name": "LEVESAM 500",
            "pack_size": "1X10",
            "batch_no": "XYZ789",
            "expiry_date": "05/27",
            "quantity": 5,
            "mrp": 250.00
        }
    }
]

# Removed redundant import

# ... (skipped imports/setup)

def run_eval():
    for i, case in enumerate(TEST_CASES):
        print(f"Running Eval Case {i+1}...")
        
        # Setup state
        state = {
            "raw_text_rows": [case["input"]],
            "global_modifiers": {"Supplier_Name": "Unknown"}
        }
        
        # Execute Mapper
        trace_id = f"eval-case-{i}-{os.urandom(4).hex()}"
        result = execute_mapping(state)
        
        fragments = result.get("line_item_fragments", [])
        extracted = fragments[0] if fragments else {}
        
        # Basic Scoring (Name check)
        score = 0
        if case["expected"]["name"] in extracted.get("description", ""):
            score = 1
        
        # Log to Langfuse
        if has_langfuse:
            langfuse.trace(
                name="Extraction-Eval",
                id=trace_id,
                input=case["input"],
                output=json.dumps(extracted)
            )
            
            langfuse.score(
                trace_id=trace_id,
                name="accuracy",
                value=score,
                comment=f"Expected: {case['expected']['name']}, Got: {extracted.get('description')}"
            )
        else:
            print(f"   -> Result: {extracted.get('description')} (Score: {score})")
            print("   -> Skipping Langfuse tracing (Keys not found)")
        
    print("Evals completed and pushed to Langfuse.")

if __name__ == "__main__":
    run_eval()
