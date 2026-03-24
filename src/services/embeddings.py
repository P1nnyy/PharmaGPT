from google import genai
import os
from typing import List
from src.utils.logging_config import get_logger
from src.utils.ai_retry import ai_retry

logger = get_logger(__name__)

# Initialize Gemini Client
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    logger.warning("GOOGLE_API_KEY not found. Embeddings will fail.")
    client = None
else:
    # Force v1 to ensure text-embedding-004 is found
    client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1'})

import requests
import json

@ai_retry
def generate_embedding(text: str) -> List[float]:
    """
    Generates a vector embedding using a direct REST API call to bypass SDK bugs.
    """
    if not text or not API_KEY: return []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}]
            },
            "outputDimensionality": 768
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        embedding = data.get("embedding", {}).get("values", [])
        
        # Final safeguard: Truncate if still larger than 768
        return embedding[:768]
    except Exception as e:
        logger.error(f"REST Embedding generation failed: {e}")
        return []
