import asyncio
from src.utils.ai_retry import is_retryable_exception
from google.genai import errors

class FakeHTTPResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self.json_data = json_data
        
    def json(self):
        return self.json_data

def test():
    # Simulate what Gemini SDK throws
    resp = FakeHTTPResponse(429, {'error': {'code': 429, 'message': 'Resource exhausted. Please try again later.'}})
    err = errors.APIError("Resource exhausted", code=429, status="RESOURCE_EXHAUSTED")
    
    print("Testing errors.APIError:", is_retryable_exception(err))

    # Also test generic string matching
    generic_err = Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource exhausted.'}}")
    print("Testing generic string matching:", is_retryable_exception(generic_err))

test()
