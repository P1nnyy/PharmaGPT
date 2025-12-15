import asyncio
import os
import logging
from dotenv import load_dotenv
load_dotenv()
from src.workflow.nodes.surveyor import survey_document
from src.workflow.nodes.worker import execute_extraction
# Mock State
state = {
    "image_path": "/Users/pranavgupta/.gemini/antigravity/brain/fcae8bf3-12a5-4747-adae-90f3c98d0f59/uploaded_image_1_1765828950383.jpg",
    "extraction_plan": []
}

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_mahajan")

async def run_test():
    print("\n--- 0. Checking Image Preprocessing ---")
    import cv2
    import numpy as np
    from src.utils.image_processing import preprocess_image_for_ocr
    
    img_bytes = preprocess_image_for_ocr(state["image_path"])
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    print(f"Processed Image Shape: {img.shape}")
    
    if img.shape[0] < 500 or img.shape[1] < 500:
        print("CRITICAL: Image is too small! Perspective Warp Failed.")

    print("--- 1. Running Surveyor ---")
    survey_result = survey_document(state)
    print(f"Survey Result: {survey_result}")
    
    if not survey_result.get("extraction_plan"):
        print("CRITICAL: Surveyor failed to find any zones!")
        return

    state["extraction_plan"] = survey_result["extraction_plan"]
    
    print("\n--- 2. Running Worker ---")
    worker_result = await execute_extraction(state)
    print(f"Worker Result: {worker_result}")

if __name__ == "__main__":
    asyncio.run(run_test())
