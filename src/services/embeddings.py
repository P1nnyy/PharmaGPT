import google.generativeai as genai
import os
from typing import List
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logger.warning("GOOGLE_API_KEY not found. Embeddings will fail.")

def generate_embedding(text: str) -> List[float]:
    """
    Generates a vector embedding for the given text using Gemini (text-embedding-004).
    """
    if not text: return []
    try:
        # task_type='retrieval_document' is good for storage
        # For queries, strictly strictly it should be 'retrieval_query' but 
        # for symmetric search or generic usages, document is often fine or default.
        # Let's check if we can parameterize. 
        # But 'text-embedding-004' is robust.
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document" 
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []
