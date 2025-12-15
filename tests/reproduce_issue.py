import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env vars BEFORE importing project modules that might check them at import time
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workflow.graph import run_extraction_pipeline
from src.utils.logging_config import get_logger

# Setup Logging to console for updates
logging = get_logger("reproduce")

async def main():
    # Updated to the new CM Associates image provided by user
    image_path = "/Users/pranavgupta/.gemini/antigravity/brain/fcae8bf3-12a5-4747-adae-90f3c98d0f59/uploaded_image_1765813406404.jpg"
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Running extraction on {image_path}...")
    try:
        final_output = await run_extraction_pipeline(image_path)
        print("\n--- RAW OUTPUT ---")
        import json
        print(json.dumps(final_output, indent=2, default=str))
        
        # normalization
        from src.normalization import normalize_line_item
        print("\n--- NORMALIZED OUTPUT (Simulating Server) ---")
        normalized_items = []
        if final_output and final_output.get("Line_Items"):
            for raw_item in final_output["Line_Items"]:
                # The workflow returns dicts, not Pydantic objects here
                norm = normalize_line_item(raw_item, final_output.get("Supplier_Name", ""))
                normalized_items.append(norm)
                
        print(json.dumps(normalized_items, indent=2, default=str))
        
        # Check if line items are empty
        if not final_output.get("Line_Items"):
            print("\nFAILURE: No line items extracted.")
        else:
            print(f"\nSUCCESS: Extracted {len(final_output['Line_Items'])} line items.")
            
    except Exception as e:
        print(f"\nCRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
