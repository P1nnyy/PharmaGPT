import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langfuse import Langfuse
# Ensure src is in path
import sys
sys.path.append(os.getcwd())

from src.services.database import connect_db, get_db_driver, close_db
from src.services.embeddings import generate_embedding
# Import the transaction function (or redefine it if reusable import is hard, but we saw it in persistence.py)
from src.domain.persistence import _create_invoice_example_tx

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gold_miner")

def mine_gold():
    load_dotenv()
    
    # 1. Init Connections
    langfuse = Langfuse()
    connect_db()
    driver = get_db_driver()
    
    if not driver:
        logger.error("Failed to connect to Neo4j.")
        return

    logger.info("Miners ready. Connecting to Langfuse to find gold...")
    
    try:
        # 2. Fetch Traces
        # Using keys from env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
        # 'page' and 'limit' might be needed.
        # We want traces with score=1 (name="user_feedback")
        
        # Note: fetch_traces might return a generator or list
        # Filters: scores
        # We look for traces where ANY score has name='user_feedback' and value=1
        
        # NOTE: SDK methods vary by version. Using robust fetch with verify.
        # If fetch_traces isn't available on the instance, we might need a separate client or API.
        # But usually `langfuse.fetch_traces()` works in 3.x
        
        page = 1
        processed = 0
        
        while True:
            response = langfuse.fetch_traces(
                page=page,
                limit=50,
                # Filtering by tags or scores varies. We'll fetch recent and filter client-side if needed
                # or assumes fetch_traces supports query params?
                # The python SDK `fetch_traces` usually takes `user_id`, `session_id`, etc.
                # It might not support deep filtering on scores directly in all versions.
                # Let's fetch last 50 traces and filter manually for simplicity and robustness.
                from_timestamp=datetime.now() - timedelta(days=1) 
            )
            
            # response.data is the list usually
            traces = response.data 
            if not traces:
                break
                
            for trace in traces:
                # Check for Score = 1
                # trace.scores is a list of Score objects
                is_gold = False
                for s in trace.scores:
                    if s.name == "user_feedback" and s.value == 1:
                        is_gold = True
                        break
                
                if is_gold:
                    logger.info(f"Gold found! Trace ID: {trace.id}")
                    process_trace(driver, trace)
                    processed += 1
            
            page += 1
            if page > 5: # Safety limit
                break
                
        logger.info(f"Mining complete. Processed {processed} gold nuggets.")
        
    except Exception as e:
        logger.error(f"Mining failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_db()

def process_trace(driver, trace):
    try:
        # Extract Data
        # trace.output should be the Final JSON
        # It might be a string or dict
        output = trace.output
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except:
                pass
                
        if not isinstance(output, dict):
            logger.warning(f"Trace {trace.id} output is not a dict. Skipping.")
            return

        raw_text = output.get("raw_text")
        supplier_name = output.get("Supplier_Name")
        
        if not raw_text or not supplier_name:
            logger.warning(f"Trace {trace.id} missing raw_text or Supplier_Name.")
            return

        # Check Duplicates in Neo4j
        # We don't want to mine the same trace twice
        # We can check by raw_text hash or just exact match
        if check_duplicate(driver, raw_text):
            logger.info(f"Trace {trace.id} already exists as example. Skipping.")
            return
            
        # Generate Embedding
        logger.info(f"Generating embedding for Trace {trace.id}...")
        embedding = generate_embedding(raw_text)
        
        if not embedding:
            logger.warning("Empty embedding. Skipping.")
            return
            
        # Save to Neo4j
        json_payload = json.dumps(output)
        
        with driver.session() as session:
            session.execute_write(
                _create_invoice_example_tx,
                supplier_name,
                raw_text,
                json_payload,
                embedding
            )
        logger.info(f"Saved InvoiceExample from Trace {trace.id} for {supplier_name}")

    except Exception as e:
        logger.error(f"Failed to process trace {trace.id}: {e}")

def check_duplicate(driver, raw_text):
    query = """
    MATCH (e:InvoiceExample)
    WHERE e.raw_text = $raw_text
    RETURN count(e) as cnt
    """
    with driver.session() as session:
        res = session.run(query, raw_text=raw_text).single()
        return res["cnt"] > 0

if __name__ == "__main__":
    mine_gold()
