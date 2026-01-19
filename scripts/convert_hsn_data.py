import sys
import os
import csv
import time

# Add project root to path
sys.path.append(os.getcwd())

from src.services.database import get_db_driver, close_db
from src.services.embeddings import generate_embedding
from src.utils.logging_config import get_logger

logger = get_logger("script.convert_hsn")

def convert_hsn_data():
    """
    Reads HSN Master CSV, generates embeddings, and saves to Neo4j.
    """
    csv_path = "config/hsn_master.csv"
    
    if not os.path.exists(csv_path):
        logger.error(f"HSN Master CSV not found at {csv_path}")
        return

    driver = get_db_driver()
    if not driver:
        logger.error("Neo4j Driver unavailable.")
        return

    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total = len(rows)
            logger.info(f"Found {total} HSN records. Starting processing...")
            
            # Prepare Query
            query = """
            MERGE (h:HSN {code: $code})
            SET h.description = $desc,
                h.embedding = $embedding,
                h.updated_at = timestamp()
            """
            
            with driver.session() as session:
                for i, row in enumerate(rows):
                    code = row.get("HSN_Code", "").strip()
                    desc = row.get("Description", "").strip()
                    
                    if not code or not desc:
                        continue
                        
                    # Generate Embedding
                    # We combine code + desc for better retrieval? Or just desc?
                    # "HSN 1234 Description of goods"
                    text_for_embedding = f"{code} {desc}"
                    try:
                        embedding = generate_embedding(text_for_embedding)
                        if not embedding:
                            logger.warning(f"Empty embedding for {code}")
                            continue
                            
                        # Run Tx
                        session.run(query, code=code, desc=desc, embedding=embedding)
                        
                        if i % 10 == 0:
                            logger.info(f"Processed {i+1}/{total}")
                            
                        # Avoid Rate Limits (Gemini limit is 15-60 RPM for free tier?)
                        # Add small sleep
                        time.sleep(1.0) 
                        
                    except Exception as e:
                        logger.error(f"Error processing {code}: {e}")

            logger.info("HSN Data Ingestion Complete.")
            
    except Exception as e:
        logger.error(f"Script Error: {e}")
    finally:
        close_db()

if __name__ == "__main__":
    convert_hsn_data()
