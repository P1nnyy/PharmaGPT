from fastapi import APIRouter, Depends
from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email
from src.utils.logging_config import get_logger
from src.domain.persistence import get_inventory

logger = get_logger(__name__)
router = APIRouter(tags=["inventory"])

@router.get("/inventory")
async def read_inventory(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return []
    try:
        data = get_inventory(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch inventory: {e}")
        return []
