
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Load Env Vars
load_dotenv()

from src.workflow.nodes.surveyor import survey_document
from src.workflow.nodes.worker import execute_extraction
from src.workflow.nodes.mapper import execute_mapping

# Configure Logging to Stdout (so we can see it in terminal)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_script")

async def run_debug_pipeline():
    # 1. Define Image Path
    # Using the path provided in user context
    image_path = "/Users/pranavgupta/.gemini/antigravity/brain/0fdbbde7-9554-45fd-80af-ee4c564702bd/uploaded_media_1769848071984.png"
    
    if not os.path.exists(image_path):
        logger.error(f"Image not found at {image_path}")
        return

    logger.info(f"--- STARTING DEBUG PIPELINE FOR: {image_path} ---")

    # Initial State
    state = {
        "image_path": image_path,
        "retry_count": 1,
        "feedback_logs": ["Previous attempt failed to extract table."]
    }

    # 2. SURVEYOR (Sync)
    logger.info("\n--- STEP 1: SURVEYOR ---")
    survey_result = survey_document(state)
    logger.info(f"Surveyor Result: {survey_result}")
    
    if "error_logs" in survey_result:
        logger.error(f"Surveyor Failed: {survey_result['error_logs']}")
        return

    state.update(survey_result)

    # 3. WORKER (Async)
    logger.info("\n--- STEP 2: WORKER ---")
    worker_result = await execute_extraction(state)
    
    # Print Raw Rows for inspection
    raw_rows = worker_result.get("raw_text_rows", [])
    logger.info(f"Worker Extracted {len(raw_rows)} Raw Rows.")
    print("\n[DEBUG] RAW TEXT ROWS START:")
    for i, row in enumerate(raw_rows):
        print(f"ROW {i}: {row[:100]}..." if len(row) > 100 else f"ROW {i}: {row}")
    print("[DEBUG] RAW TEXT ROWS END\n")
    
    if "error_logs" in worker_result and worker_result["error_logs"]:
        logger.error(f"Worker Reported Errors: {worker_result['error_logs']}")
    
    state.update(worker_result)

    # 4. MAPPER (Sync)
    logger.info("\n--- STEP 3: MAPPER ---")
    mapper_result = execute_mapping(state)
    logger.info(f"Mapper Result Key: {mapper_result.keys()}")
    
    items = mapper_result.get("line_item_fragments", [])
    logger.info(f"Mapper Extracted {len(items)} Valid Items.")
    
    if items:
        print("\n[DEBUG] MAPPED ITEMS SAMPLE:")
        import json
        print(json.dumps(items[0], indent=2))
    else:
        logger.warning("Mapper output is EMPTY!")
        if "error_logs" in mapper_result:
             logger.error(f"Mapper Errors: {mapper_result['error_logs']}")

    logger.info("--- DEBUG PIPELINE COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_debug_pipeline())
