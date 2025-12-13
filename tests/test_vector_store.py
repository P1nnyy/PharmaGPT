import sys
import os
# Add src to path
sys.path.append(os.getcwd())

from src.services.hsn_vector_store import HSNVectorStore

def test_vector_store():
    print("Initializing Vector Store...")
    store = HSNVectorStore()
    
    csv_path = "config/hsn_master.csv"
    print(f"Ingesting from {csv_path}...")
    store.ingest_hsn_csv(csv_path)
    
    print("Testing Search...")
    queries = [
        "Paracetamol 500mg tablet",
        "Insulin injection",
        "Cotton Bandage",
        "Durtelli 100mg" # Random noise
    ]
    
    for q in queries:
        res = store.search_hsn(q)
        print(f"Query: '{q}' -> Result: {res}")

if __name__ == "__main__":
    test_vector_store()
