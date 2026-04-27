import os
import json
import chromadb
from dotenv import load_dotenv
from google import genai

load_dotenv()

from src.services.embeddings import generate_embedding

def embed_text(text: str):
    return generate_embedding(text)

def train_mistake():
    print("Migrating mistakes.json to ChromaDB...")
    
    mistakes_file = "data/mistakes.json"
    if not os.path.exists(mistakes_file):
        print(f"Error: {mistakes_file} not found.")
        return
        
    with open(mistakes_file, "r") as f:
        data = json.load(f)
        rules = data.get("rules", [])
        
    if not rules:
        print("No rules found in mistakes.json")
        return
        
    # Setup ChromaDB Persistent Storage
    os.makedirs("./data/chroma", exist_ok=True)
    chroma_client = chromadb.PersistentClient(path="./data/chroma")
    
    # Get or create collection
    collection = chroma_client.get_or_create_collection(
        name="vendor_guardrails",
        metadata={"hnsw:space": "cosine"}
    )
    
    ids = []
    documents = []
    embeddings = []
    
    print(f"Embedding {len(rules)} rules...")
    for i, rule in enumerate(rules):
        ids.append(f"rule_{i}")
        documents.append(rule)
        emb = embed_text(rule)
        if not emb:
            print(f"Failed to generate embedding for rule {i}, skipping.")
            continue
        embeddings.append(emb)
        print(f"  -> Generated embedding for rule_{i}")
        
    print("Upserting arrays to ChromaDB collection 'vendor_guardrails'...")
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents
    )
    
    count = collection.count()
    print(f"Migration Complete. Total operational constraints in vector DB: {count}")

if __name__ == "__main__":
    train_mistake()
