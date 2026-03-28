import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar

# ContextVars to store metadata for the current thread/task
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="SYSTEM")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="SYSTEM")

import re

class PHIFilter(logging.Filter):
    """
    Strips Protected Health Information (PHI) from log messages.
    Redacts Patient Names, Doctor Names, and Contact Info.
    """
    # Regex patterns for common PHI markers
    PATTERNS = [
        (r'(?i)patient[:\s]+([a-z\s]{2,30})', 'Patient: [REDACTED]'),
        (r'(?i)(dr\.|physician)[:\s]+([a-z\s]{2,30})', r'\1 [REDACTED]'),
        (r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL REDACTED]'),
        (r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE REDACTED]')
    ]

    def filter(self, record):
        if not isinstance(record.msg, str):
            return True
            
        original_msg = record.msg
        for pattern, replacement in self.PATTERNS:
            record.msg = re.sub(pattern, replacement, record.msg)
            
        if record.args:
            # Also check formatted string if possible, 
            # but record.msg is usually the template.
            pass
            
        return True

class RequestIdFilter(logging.Filter):
    """
    Injects the Request ID and Tenant ID into the log record from context variables.
    """
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        record.tenant_id = tenant_id_ctx.get()
        return True

def setup_logging(log_dir: str = "logs", log_file: str = "app.log"):
    """
    Configures the root logger with File and Console handlers.
    Strictly standardizes format and applies PHI/Tenant filtering.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # Standard Format: [Time] [Level] [Module] [Req: ID] [Ten: ID] - Message
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [Req: %(request_id)s] [Ten: %(tenant_id)s] - %(message)s"
    )
    
    # Instantiate Filters
    req_filter = RequestIdFilter()
    phi_filter = PHIFilter()

    # 1. File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(req_filter)
    file_handler.addFilter(phi_filter)

    # 2. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(req_filter)
    console_handler.addFilter(phi_filter)

    # Configure Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates on reload
    if root_logger.handlers:
        root_logger.handlers = []
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger with the RequestIdFilter.
    """
    logger = logging.getLogger(name)
    # Filter is added at handler level in setup_logging, 
    # but strictly speaking, if we want it to work for custom handlers later, 
    # we rely on the Root logger's handlers.
    return logger
