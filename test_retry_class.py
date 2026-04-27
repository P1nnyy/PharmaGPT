import asyncio
import logging
from src.utils.ai_retry import ai_retry

logging.basicConfig(level=logging.WARNING)

class TestClient:
    def __init__(self):
        self.attempts = 0

    @ai_retry
    async def call_api(self):
        self.attempts += 1
        print(f"Attempt {self.attempts}")
        raise Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}")

async def main():
    client = TestClient()
    try:
        await client.call_api()
    except Exception as e:
        print("Final error:", e)

asyncio.run(main())
