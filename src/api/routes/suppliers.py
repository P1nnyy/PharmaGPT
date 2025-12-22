from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from src.database import get_supplier_history
from src.database.connection import get_driver
from src.utils.logging_config import get_logger

logger = get_logger("api.suppliers")
router = APIRouter()

class EnrichmentRequest(BaseModel):
    supplier_name: str

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_history_endpoint():
    """
    Returns grouped invoice history by Supplier.
    """
    driver = get_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        return get_supplier_history(driver)
    except Exception as e:
        logger.error(f"History Fetch Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrich-supplier")
async def enrich_supplier_endpoint(request: EnrichmentRequest):
    """
    Triggers an Agent to find missing GST/Phone for a Supplier.
    """
    # TODO: Implement LangGraph Agent
    return {"status": "queued", "message": f"Enrichment started for {request.supplier_name}"}
