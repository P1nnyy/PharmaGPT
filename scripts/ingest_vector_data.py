import sys
import os
import json
import time

# Add project root to path
sys.path.append(os.getcwd())

from src.services.database import get_db_driver, close_db
from src.services.embeddings import generate_embedding
from src.utils.logging_config import get_logger

# Import the TX function directly if possible, or replicate query
from src.domain.persistence import _create_invoice_example_tx

logger = get_logger("script.ingest_vector")

DATA_FILE = "data/invoice_examples.json"

def create_dummy_data():
    examples = [
        {
            "supplier": "Deepak Agencies",
            "raw_text": "DEEPAK AGENCIES GSTIN: 07AABC... INV: 101 ... Tab Dolo 650 Qty 10 Rate 15.00",
            "json_payload": json.dumps({
                "Invoice_No": "101",
                "Supplier_Name": "Deepak Agencies",
                "Grand_Total": 150.0
            })
        }
    ]
    with open(DATA_FILE, "w") as f:
        json.dump(examples, f, indent=2)
    logger.info(f"Created dummy {DATA_FILE}")

def ingest_vector_data():
    """
    Ingests Invoice Examples from JSON to Neo4j Vector Index.
    """
    if not os.path.exists(DATA_FILE):
        create_dummy_data()
        
    driver = get_db_driver()
    if not driver:
        return

    try:
        with open(DATA_FILE, "r") as f:
            examples = json.load(f)
            
        logger.info(f"Found {len(examples)} examples. Starting ingestion...")
        
        with driver.session() as session:
            for ex in examples:
                supplier = ex.get("supplier")
                raw_text = ex.get("raw_text")
                json_payload = ex.get("json_payload")
                
                # Check if JSON object or string
                if isinstance(json_payload, dict):
                    json_payload = json.dumps(json_payload)
                    
                if not raw_text:
                    continue
                    
                # Generate Embedding
                embedding = generate_embedding(raw_text)
                if not embedding:
                    logger.warning(f"Failed embedding for {supplier}")
                    continue
                    
                # Save to Neo4j
                session.execute_write(_create_invoice_example_tx, supplier, raw_text, json_payload, embedding)
                logger.info(f"Ingested example for {supplier}")
                
                time.sleep(1.0) # Rate limit protection

        logger.info("Vector Ingestion Complete.")

    except Exception as e:
        logger.error(f"Ingest Error: {e}")
    finally:
        close_db()

if __name__ == "__main__":
    ingest_vector_data()
