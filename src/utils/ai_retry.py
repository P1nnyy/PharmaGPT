import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log
)
from google.genai import errors

logger = logging.getLogger("ai_retry")

def is_retryable_exception(exception):
    """
    Checks if the exception is a 429 (Rate Limit) or 5xx (Server Error).
    """
    try:
        # 1. New google-genai error handling
        if isinstance(exception, errors.APIError):
            if getattr(exception, 'code', None) == 429:
                return True
            if 500 <= (getattr(exception, 'code', 0) or 0) < 600:
                return True
        
        # 2. Legacy/Generic Check for robustness
        err_str = str(exception).lower()
        if "429" in err_str or "resource exhausted" in err_str:
            return True
        if "500" in err_str or "503" in err_str or "service unavailable" in err_str:
            return True
            
        return False
    except Exception as check_e:
        # Failsafe: if our check fails, don't crash tenacious loops blindly
        err_str = str(exception).lower()
        if "429" in err_str or "resource" in err_str:
            return True
        return False

# Reusable retry decorator
ai_retry = retry(
    retry=retry_if_exception(is_retryable_exception),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
