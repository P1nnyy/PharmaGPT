import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import pandas as pd
import os
import logging
from typing import Optional, List

# Configure logger
logger = logging.getLogger(__name__)

class HSNVectorStore:
    def __init__(self, persist_dir: str = "./data/chroma_db"):
        """
        Initializes the ChromaDB client and SentenceTransformer model.
        """
        try:
            # Initialize persistent client
            self.client = chromadb.PersistentClient(path=persist_dir)
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(name="hsn_codes")
            
            # Initialize embedding model (lightweight)
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            
            logger.info(f"HSNVectorStore initialized at {persist_dir}")
            
        except Exception as e:
            logger.error(f"Failed to initialize HSNVectorStore: {e}")
            raise e

    def ingest_hsn_csv(self, csv_path: str):
        """
        Ingests HSN codes from a CSV file into ChromaDB.
        Expected CSV columns: 'HSN_Code', 'Description'
        """
        try:
            if not os.path.exists(csv_path):
                logger.error(f"CSV file not found: {csv_path}")
                return

            # Check if collection is already populated to avoid duplicates
            if self.collection.count() > 0:
                logger.info("HSN Collection already contains data. Skipping ingestion.")
                return

            df = pd.read_csv(csv_path)
            
            # Clean and validate headers
            # Assuming 'HSN_Code' and 'Description' exist based on user prompt context
            # If actual CSV has different headers, this might need adjustment.
            # Standardizing headers
            df.columns = [c.strip() for c in df.columns]
            
            required_cols = ['HSN_Code', 'Description']
            if not all(col in df.columns for col in required_cols):
                 # Fallback logic if names match vaguely? 
                 # For now, let's assume strict names or 'HSN Code'/'Item Description'
                 pass

            documents = []
            metadatas = []
            ids = []

            logger.info("Generating embeddings for HSN Master...")
            
            for idx, row in df.iterrows():
                hsn = str(row.get('HSN_Code', '')).strip()
                desc = str(row.get('Description', '')).strip()
                
                if not hsn or not desc:
                    continue

                documents.append(desc)
                metadatas.append({"hsn_code": hsn})
                ids.append(f"hsn_{idx}")
            
            if not documents:
                logger.warning("No valid rows found to ingest.")
                return

            # Compute embeddings
            embeddings = self.model.encode(documents).tolist()

            # Add to Chroma
            batch_size = 500
            total = len(documents)
            
            for i in range(0, total, batch_size):
                end = min(i + batch_size, total)
                self.collection.add(
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )
                logger.info(f"Ingested batch {i}-{end} / {total}")
            
            logger.info("HSN Ingestion Complete.")

        except Exception as e:
            logger.error(f"Error during HSN Ingestion: {e}")

    def search_hsn(self, description: str, limit: int = 1, threshold: float = 1.0) -> Optional[str]:
        """
        Semantically searches for an HSN code based on product description.
        Returns the top matching HSN Code if distance < threshold.
        """
        try:
            if not description or not description.strip():
                return None
                
            query_embedding = self.model.encode([description]).tolist()
            
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=limit
            )
            
            # Results structure: {'ids': [['id1']], 'distances': [[0.2]], 'metadatas': [[{'hsn_code': '...' }]]}
            
            if not results['ids'] or not results['ids'][0]:
                return None
                
            distance = results['distances'][0][0]
            
            if distance < threshold:
                hsn_code = results['metadatas'][0][0].get('hsn_code')
                logger.info(f"Vector Match: '{description}' -> {hsn_code} (Dist: {distance:.4f})")
                return hsn_code
            else:
                logger.info(f"Vector Mismatch: '{description}' closest dist {distance:.4f} > {threshold}")
                return None

        except Exception as e:
            logger.error(f"Error searching HSN: {e}")
            return None
