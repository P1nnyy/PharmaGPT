import os
import asyncio
from google import genai
from src.utils.logging_config import get_logger
from src.utils.ai_retry import ai_retry

logger = get_logger("ai_client")

class AIClientManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIClientManager, cls).__new__(cls)
            cls._instance._client = None
        return cls._instance

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                self._client = genai.Client(api_key=api_key)
            else:
                logger.error("GOOGLE_API_KEY not found. AI features will fail.")
        return self._client

    @ai_retry
    async def generate_content_async(self, model: str, contents: list, **kwargs):
        """
        Async wrapper for Gemini generate_content. Relies on the ai_retry decorator for rate limit backoff.
        """
        if not self.client:
            raise RuntimeError("Gemini Client not initialized (Missing API Key)")

        if not hasattr(self, "_semaphore") or self._semaphore is None:
            self._semaphore = asyncio.Semaphore(2)

        async with self._semaphore:
            # Use aio for non-blocking IO
            return await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                **kwargs
            )

    @ai_retry
    async def upload_file_async(self, file_path: str):
        """
        Async wrapper for file uploading.
        """
        if not self.client:
            raise RuntimeError("Gemini Client not initialized")

        # Offload sync upload to a thread to avoid blocking the event loop
        sample_file = await asyncio.to_thread(self.client.files.upload, file=file_path)
        return sample_file

    @ai_retry
    async def create_cached_content_async(self, model: str, contents: list, ttl_seconds: int = 900):
        """
        Async wrapper to create Gemini Context Caching.
        Catches 400 errors silently if the request size is beneath the 4096 token minimum.
        """
        from google.genai import types
        if not self.client:
            raise RuntimeError("Gemini Client not initialized")
            
        try:
            return await self.client.aio.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    contents=contents,
                    ttl=f"{ttl_seconds}s"
                )
            )
        except Exception as e:
            if "total_token_count" in str(e) or "400" in str(e):
                logger.warning(f"Cache rejected (too small or invalid): {e}. Proceeding without caching.")
                return None
            raise e

    def generate_content_sync(self, model: str, contents: list, **kwargs):
        """
        Sync wrapper (Legacy/Fallback). 
        Does NOT use the semaphore safely across threads, so use async instead.
        """
        if not self.client:
            raise RuntimeError("Gemini Client not initialized")
        return self.client.models.generate_content(model=model, contents=contents, **kwargs)

# Singleton Instance
manager = AIClientManager()
