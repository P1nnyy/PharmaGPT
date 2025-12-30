import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar

# ContextVar to store Request ID for the current thread/task
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="SYSTEM")

class RequestIdFilter(logging.Filter):
    """
    Injects the Request ID into the log record.
    """
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        return True

def setup_logging(log_dir: str = "logs", log_file: str = "app.log"):
    """
    Configures the root logger with File and Console handlers.
    Strictly standardizes format for easy parsing.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # Standard Format: [Time] [Level] [Module] [Req: ID] - Message
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [Req: %(request_id)s] - %(message)s"
    )

    # 1. File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RequestIdFilter())

    # 2. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIdFilter())

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
