import os
import asyncio
from google import genai
from src.utils.logging_config import get_logger

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


    async def generate_content_async(self, model: str, contents: list, **kwargs):
        """
        Async wrapper for Gemini generate_content. Relies on tenacity for rate limit backoff.
        """
        if not self.client:
            raise RuntimeError("Gemini Client not initialized (Missing API Key)")

        # Use aio for non-blocking IO
        return await self.client.aio.models.generate_content(
            model=model,
            contents=contents,
            **kwargs
        )

    async def upload_file_async(self, file_path: str):
        """
        Async wrapper for file uploading.
        """
        if not self.client:
            raise RuntimeError("Gemini Client not initialized")

        # Offload sync upload to a thread to avoid blocking the event loop
        sample_file = await asyncio.to_thread(self.client.files.upload, file=file_path)
        return sample_file

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
