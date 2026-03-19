import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log
)
import google.api_core.exceptions

logger = logging.getLogger("ai_retry")

def is_retryable_exception(exception):
    """
    Checks if the exception is a 429 (Rate Limit) or 5xx (Server Error).
    """
    if isinstance(exception, (google.api_core.exceptions.ResourceExhausted, 
                              google.api_core.exceptions.ServiceUnavailable,
                              google.api_core.exceptions.InternalServerError)):
        return True
    
    # Also check string representation for generic 429/500 errors from SDK
    err_str = str(exception).lower()
    if "429" in err_str or "resource exhausted" in err_str:
        return True
    if "500" in err_str or "503" in err_str or "service unavailable" in err_str:
        return True
        
    return False

# Reusable retry decorator
ai_retry = retry(
    retry=retry_if_exception(is_retryable_exception),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
