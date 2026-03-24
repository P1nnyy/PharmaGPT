import sys
import os
import asyncio
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from src.workflow.graph import run_extraction_pipeline
from src.domain.schemas import InvoiceExtraction
from src.utils.logging_config import setup_logging

setup_logging()

async def reproduce_full():
    image_path = "tmp/failed_invoice.jpeg"
    user_email = "pranavgupta1638@gmail.com"
    
    print(f"Running extraction pipeline for {image_path}...")
    
    try:
        # 1. Run Pipeline
        extracted_data = await run_extraction_pipeline(image_path, user_email)
        
        print("\n--- Pipeline Output (Partial) ---")
        # print(json.dumps(extracted_data, indent=2))
        
        # 2. Key Fields Check
        print(f"Items Found: {len(extracted_data.get('Line_Items', []))}")
        print(f"taxable_value: {extracted_data.get('taxable_value')}")
        print(f"sub_total: {extracted_data.get('sub_total')}")
        
        # 3. Pydantic Validation Check (This is where the backend was crashing)
        print("\nAttempting Pydantic Validation...")
        invoice_obj = InvoiceExtraction(**extracted_data)
        print("Success! Pydantic validation passed.")
        
    except Exception as e:
        print(f"\nCaught Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce_full())
