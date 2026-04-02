from fastapi import APIRouter, Depends
from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email
from src.utils.logging_config import get_logger, tenant_id_ctx
from src.domain.persistence import get_inventory

logger = get_logger(__name__)
router = APIRouter(tags=["inventory"])

@router.get("/inventory")
async def read_inventory(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return []
    try:
        shop_id = tenant_id_ctx.get()
        data = get_inventory(driver, shop_id, shop_id)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch inventory: {e}")
        return []
