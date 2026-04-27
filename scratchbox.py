import asyncio
from src.utils.ai_retry import is_retryable_exception

class FakeException(Exception):
    pass

e = FakeException("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}")
print("fake:", is_retryable_exception(e))
