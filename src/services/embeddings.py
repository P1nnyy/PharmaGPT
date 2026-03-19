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
    client = genai.Client(api_key=API_KEY)

@ai_retry
def generate_embedding(text: str) -> List[float]:
    """
    Generates a vector embedding for the given text using the new Google Gen AI SDK.
    """
    if not text or not client: return []
    try:
        # Use text-embedding-004 which is the current best model
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        # Note: The new SDK returns embeddings in a slightly different structure
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []
