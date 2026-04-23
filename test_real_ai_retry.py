import asyncio
import time
from src.utils.ai_retry import ai_retry

class TestClient:
    def __init__(self):
        self.attempts = 0

    @ai_retry
    async def do_something(self):
        self.attempts += 1
        print(f"Attempt: {self.attempts}")
        raise Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED'}}")

async def main():
    t = TestClient()
    start = time.time()
    try:
        await t.do_something()
    except Exception as e:
        print(f"Failed after {time.time() - start:.2f}s with {t.attempts} attempts")

asyncio.run(main())
