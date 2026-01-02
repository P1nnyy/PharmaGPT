import os
import sys
import json
from dotenv import load_dotenv

# Load Env (Credentials)
load_dotenv()

from src.services.embeddings import generate_embedding
from src.services.database import get_db_driver

# Manually ingest a correction for ATORLIP F
def train_mistake():
    print("Training Model with Correction for ATORLIP F...")
    
    # 1. Simulate the Raw Text (The "Mistake" Context)
    # We simulate what the OCR likely saw (ambiguous spacing or column)
    # "14 ATORLIP F 4 348.66" -> mistook 4 for something else or missed it?
    # User said "invoice had mentioned 4 items but model printed out it as 1"
    raw_text_simulation = """
    14 ATORLIP F 4 87.16 348.66
    """
    
    # 2. The Correct Extraction (The "Lesson")
    correct_json = {
        "line_items": [
            {
                "Product": "ATORLIP F",
                "Qty": 4.0,
                "Rate": 87.16,
                "Amount": 348.66,
                "Batch": "Unknown", # Optional
                "Expiry": "Unknown"
            }
        ]
    }
    json_payload = json.dumps(correct_json)
    
    # 3. Generate Embedding
    print("Generating Embedding...")
    embedding = generate_embedding(raw_text_simulation)
    
    if not embedding:
        print("Error: Failed to generate embedding.")
        return

    # 4. Save to Neo4j
    from src.services.database import connect_db
    connect_db() # Initialize Driver
    
    driver = get_db_driver()
    if not driver:
        print("Error: Could not connect to Database.")
        return

    query = """
    CREATE (e:InvoiceExample {
        raw_text: $raw_text,
        json_payload: $json_payload,
        created_at: timestamp(),
        note: 'Manual Correction for ATORLIP F (Qty 4 vs 1)'
    })
    SET e.embedding = $embedding
    
    // Link to a Generic/System Supplier or match inferred
    // For now, just leaving it standalone or linking to a 'System' node if we wanted
    // But vector search finds it globaly usually? 
    // Mapper query: CALL db.index.vector.queryNodes('invoice_examples_index', 1, $embedding)
    // It queries NODES. So it doesn't strictly need a relationship to be found.
    // Ensure the index exists though.
    """
    
    try:
        with driver.session() as session:
            session.run(query, 
                       raw_text=raw_text_simulation,
                       json_payload=json_payload,
                       embedding=embedding)
        print("Successfully ingested correction into Vector Database.")
    except Exception as e:
        print(f"Failed to save to Neo4j: {e}")

if __name__ == "__main__":
    train_mistake()
