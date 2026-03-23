import os
import asyncio
from google import genai
from src.utils.logging_config import get_logger

logger = get_logger("ai_client")

class AIClientManager:
    _instance = None
    _client = None
    _semaphore = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIClientManager, cls).__new__(cls)
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY not found. AI features will fail.")
            
            cls._client = genai.Client(api_key=api_key) if api_key else None
            # Global limit: 2 concurrent requests to Gemini across the whole app
            # Lowered from 3 to 2 to avoid 429 errors on free/low tiers
            cls._semaphore = asyncio.Semaphore(2)
            logger.info("AIClientManager: Initialized with concurrency limit = 2")
        return cls._instance

    @property
    def client(self):
        return self._client

    @property
    def semaphore(self):
        return self._semaphore

    async def generate_content_async(self, model: str, contents: list, **kwargs):
        """
        Async wrapper for Gemini generate_content with global semaphore.
        """
        if not self._client:
            raise RuntimeError("Gemini Client not initialized (Missing API Key)")

        async with self._semaphore:
            logger.debug(f"AIClientManager: Semaphore Acquired for generation. Task: {asyncio.current_task().get_name()}")
            try:
                # Use aio for non-blocking IO
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    **kwargs
                )
                return response
            finally:
                logger.debug("AIClientManager: Semaphore Released (generation).")

    async def upload_file_async(self, file_path: str):
        """
        Throttled async wrapper for file uploading.
        Ensures even uploads respect the global AI concurrency limit.
        """
        if not self._client:
            raise RuntimeError("Gemini Client not initialized")

        async with self._semaphore:
            logger.debug(f"AIClientManager: Semaphore Acquired for upload: {os.path.basename(file_path)}")
            try:
                # Note: The SDK's upload method is currently sync but we wrap it 
                # to respect the async semaphore and keep the interface async.
                # If a large file blocks, it blocks this task but we still respect the limit.
                sample_file = self._client.files.upload(file=file_path)
                return sample_file
            finally:
                logger.debug(f"AIClientManager: Semaphore Released (upload): {os.path.basename(file_path)}")

    def generate_content_sync(self, model: str, contents: list, **kwargs):
        """
        Sync wrapper (Legacy/Fallback). 
        Does NOT use the semaphore safely across threads, so use async instead.
        """
        if not self._client:
            raise RuntimeError("Gemini Client not initialized")
        return self._client.models.generate_content(model=model, contents=contents, **kwargs)

# Singleton Instance
manager = AIClientManager()
