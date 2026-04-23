import asyncio
from src.services.ai_client import manager
from google.genai import errors
import logging
logging.basicConfig(level=logging.WARNING)

async def test():
    try:
        # Pass an invalid model to force an error, or we can mock it
        # Actually let's just mock the generate_content
        original = manager.client.aio.models.generate_content
        async def mock_generate(*args, **kwargs):
            raise Exception("429 RESOURCE EXHAUSTED")
        manager.client.aio.models.generate_content = mock_generate
        
        await manager.generate_content_async(model="gemini-2.0-flash", contents=["hi"])
    except Exception as e:
        print(f"Final caught: {e}")

asyncio.run(test())
