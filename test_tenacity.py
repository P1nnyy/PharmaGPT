import asyncio
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("test")

def is_local_retryable(e):
    print(f"Checking if retryable: {e}")
    return True

ai_retry = retry(
    retry=retry_if_exception(is_local_retryable),
    wait=wait_fixed(1),
    stop=stop_after_attempt(3),
    reraise=True
)

class TestClass:
    @ai_retry
    async def do_work(self):
        print("Doing work...")
        raise ValueError("Failed!")

async def main():
    t = TestClass()
    try:
        await t.do_work()
    except Exception as e:
        print(f"Caught: {e}")

asyncio.run(main())
