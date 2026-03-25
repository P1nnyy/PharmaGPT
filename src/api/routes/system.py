import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from langfuse import Langfuse
from src.api.routes.auth import get_current_user_email
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/system", tags=["system"])

class FeedbackRequest(BaseModel):
    trace_id: str
    score: int
    comment: str = None

@router.get("/health")
async def health_check():
    """
    Native health check endpoint.
    Checks database connectivity and basic system status.
    """
    health_status = {
        "status": "unhealthy",
        "components": {
            "api": "healthy",
            "database": "unknown",
            "storage": "unknown"
        }
    }
    
    # Check Database
    from src.services.database import get_db_driver
    try:
        # Simple ping/query
        driver = get_db_driver()
        if driver:
            health_status["components"]["database"] = "healthy"
        else:
            health_status["components"]["database"] = "disconnected"
    except Exception as e:
        logger.error(f"Healthcheck Database Error: {e}")
        health_status["components"]["database"] = f"error: {str(e)}"

    # Check Storage (R2)
    from src.services.storage import get_storage_client
    try:
        client = get_storage_client()
        if client:
            health_status["components"]["storage"] = "healthy"
    except Exception as e:
        logger.error(f"Healthcheck Storage Error: {e}")
        health_status["components"]["storage"] = f"error: {str(e)}"

    # Overall Status
    if all(v == "healthy" for v in health_status["components"].values()):
        health_status["status"] = "healthy"
        return health_status
    
    # Partial failure still returns 200 for now but with status="unhealthy"
    # Or should we return 503?
    return health_status

@router.get("/logs")
async def get_logs(lines: int = 100, user_email: str = Depends(get_current_user_email)):
    """
    Retrieves the last N lines of the application log.
    Useful for debugging without SSH access.
    """
    log_file = "logs/app.log"
    if not os.path.exists(log_file):
        return {"error": "Log file not found."}
        
    try:
        with open(log_file, "r") as f:
            content = f.readlines()
            # Return last N lines
            recent = content[-lines:]
            return {"logs": recent}
    except Exception as e:
        return {"error": f"Failed to read logs: {str(e)}"}

@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, user_email: str = Depends(get_current_user_email)):
    """
    Submits feedback (score) to Langfuse for a given trace.
    """
    try:
        langfuse = Langfuse() # Auto-loads keys from env
        # Score: 1 = Good (Thumbs Up), 0 = Bad (Thumbs Down)
        langfuse.score(
            trace_id=feedback.trace_id,
            name="user_feedback",
            value=feedback.score,
            comment=feedback.comment
        )
        # Flush to ensure it sends immediately (optional but good for low volume)
        langfuse.flush()
        return {"status": "success", "message": "Feedback submitted"}
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        # Don't crash the UI for feedback failure
        return {"status": "error", "message": str(e)}
