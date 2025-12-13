from src.services.hsn_vector_store import HSNVectorStore
import pandas as pd
import os
import sys

def ingest_data():
    csv_path = "config/hsn_master.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run convert_hsn_data.py first.")
        sys.exit(1)

    print("Initializing Vector Store...")
    store = HSNVectorStore()
    
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Optional: Limit for testing? No, user wants full pop.
    # df = df.head(100) 
    
    print(f"Ingesting {len(df)} records into ChromaDB...")
    try:
        store.ingest_hsn_csv(csv_path)
        print("Ingestion complete!")
        
        # Simple verify
        print("Running test query for 'Paracetamol'...")
        res = store.search_hsn("Paracetamol")
        print(f"Test Result: {res}")
        
    except Exception as e:
        print(f"Ingestion failed: {e}")

if __name__ == "__main__":
    ingest_data()
