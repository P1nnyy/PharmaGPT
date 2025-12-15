import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Load Env BEFORE importing local modules that use it
print(f"CWD: {os.getcwd()}")
env_path = os.path.join(os.getcwd(), ".env")
print(f"Env Path: {env_path}, Exists: {os.path.exists(env_path)}")
loaded = load_dotenv(env_path, override=True)
print(f"Load Dotenv Result: {loaded}")

# Add src to path
sys.path.append(os.getcwd())

from src.workflow.graph import run_extraction_pipeline
from src.workflow.nodes.surveyor import survey_document
from src.workflow.nodes.worker import execute_extraction
from src.workflow.nodes.auditor import audit_extraction
import google.generativeai as genai

from src.utils.logging_config import setup_logging, get_logger

# Initialize Logger
setup_logging()
logger = get_logger("debug_script")

# Setup
API_KEY = os.getenv("GOOGLE_API_KEY")
print(f"API Key Found: {bool(API_KEY)}")
if API_KEY:
    genai.configure(api_key=API_KEY)

from src.utils.logging_config import setup_logging
setup_logging(log_dir="logs", log_file="debug.log") # Separate log for this script

async def debug_pipeline():
    # Use the file from the logs, or a known sample. 
    # Based on logs: /var/folders/47/928ljscj1p59cn2x2vqg9gw00000gn/T/tmpt9sfmesy.jpeg was used.
    # But that's a temp file that might be gone.
    # Using a sample from artifacts if available, or just printing "Please Provide Path"
    # Actually, let's use the one in the code if it exists, or one from artifacts.
    image_path = "/Users/pranavgupta/.gemini/antigravity/brain/274fe64f-1c46-4dd9-8ab6-d8b117f77ac9/uploaded_image_1765647732313.png" # Existing artifact
    
    if not os.path.exists(image_path):
        # Try to find ANY png in artifacts
        artifact_dir = "/Users/pranavgupta/.gemini/antigravity/brain/274fe64f-1c46-4dd9-8ab6-d8b117f77ac9"
        files = [f for f in os.listdir(artifact_dir) if f.endswith(".png")]
        if files:
            image_path = os.path.join(artifact_dir, files[0])
            print(f"Fallback to Artifact: {image_path}")
    
    print(f"--- Debugging Image: {image_path} ---")
    
    if not os.path.exists(image_path):
        print("Image not found!")
        return

    # 1. Run Surveyor manually
    print("\n[1] Running Surveyor...")
    
    # We need to simulate the state passed to surveyor? 
    # Actually surveyor takes 'state'.
    state = {"image_path": image_path, "extraction_plan": [], "line_item_fragments": [], "global_modifiers": {}}
    survey_res = survey_document(state)
    plan = survey_res.get("extraction_plan", [])
    print(f"Surveyor Found {len(plan)} zones:")
    for z in plan:
        print(f" - {z}")

    # 2. Run Full Pipeline
    print("\n[2] Running Full Pipeline (Worker + Auditor + Normalization)...")
    try:
        final_output = await run_extraction_pipeline(image_path)
        # Use Capital 'Line_Items' as per final output schema
        items = final_output.get("Line_Items", [])
        logger.info(f"Pipeline Extracted {len(items)} items.")
        
        logger.info("\n--- Final Normalized Items ---")
        # Also print keys to verify Headers exists
        logger.info(f"Final Keys: {list(final_output.keys())}")
        
        if "Invoice_No" not in final_output:
            logger.error("CRITICAL ERROR: Headers missing in final output!")
        else:
            logger.info(f"Success: Invoice No '{final_output.get('Invoice_No')}' found.")
            
        for i, item in enumerate(items):
            desc = item.get("Original_Product_Description", "")
            qty = item.get("Raw_Quantity", 0)
            net = item.get("Invoice_Line_Amount", 0.0) or item.get("Stated_Net_Amount", 0.0)
            batch = item.get("Batch_No", "N/A")
            logger.info(f"ROW [{i}] {desc} | Qty: {qty} | Batch: {batch} | Net: {net}")
            
    except Exception as e:
        print(f"Pipeline Error: {e}")
        import traceback
        traceback.print_exc()

    return

    # Skip manual worker/auditor steps below since we ran the full pipeline
    """
    # 2. Run Worker manually
    print("\n[2] Running Worker...")
    state["extraction_plan"] = plan
    worker_res = await execute_extraction(state)
    raw_items = worker_res.get("line_item_fragments", [])
    print(f"Worker Extracted {len(raw_items)} fragments.")
    
    print("\n--- Raw Fragment Signatures ---")
    for i, item in enumerate(raw_items):
        desc = str(item.get("Original_Product_Description", "")).strip()
        net = str(item.get("Stated_Net_Amount", "")).strip()
        batch = str(item.get("Batch_No", "")).strip()
        rate = str(item.get("Raw_Rate_Column_1", "N/A"))
        qty = str(item.get("Raw_Quantity", "N/A"))
        print(f"[{i}] {desc} | Qty: {qty} | Rate: {rate} | Net: {net} | Batch: {batch}")

    # 3. Simulate Auditor Deduplication
    print("\n[3] Simulating Auditor Deduplication...")
    unique_items_map = {}
    deduped_items = []
    
    for item in raw_items:
        desc = str(item.get("Original_Product_Description", "")).strip()
        net = str(item.get("Stated_Net_Amount", "")).strip()
        # Clean net amount to remove float variance if any?
        # The auditor uses strict string comparison currently.
        
        batch = str(item.get("Batch_No", "")).strip()
        
        signature = (desc, net, batch)
        
        # Check noise filter logic too
        try:
            n_val = float(item.get("Stated_Net_Amount") or 0)
            q_val = float(item.get("Raw_Quantity") or 0)
            if n_val == 0.0 and q_val == 0.0:
                print(f"   -> Filtered as Noise: {signature}")
                continue
        except:
            pass

        if signature not in unique_items_map:
            unique_items_map[signature] = True
            deduped_items.append(item)
            print(f"   -> KEEP: {signature}")
        else:
            print(f"   -> DUPLICATE: {signature}")

    print(f"\nFinal Count: {len(deduped_items)}")
    """

if __name__ == "__main__":
    asyncio.run(debug_pipeline())

