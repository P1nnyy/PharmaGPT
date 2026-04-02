from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email, get_current_user_role
from src.utils.logging_config import get_logger, tenant_id_ctx
from src.domain.persistence import (
    get_activity_log,
    get_grouped_invoice_history,
    get_invoice_details
)

logger = get_logger(__name__)
router = APIRouter(tags=["reporting"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

# Note: Templates directory path might need adjustment. 
# src/api/templates implies ../templates from this file (src/api/routes/reporting.py).
# server.py was in src/api/server.py so it used os.path.dirname(__file__) + "templates".
# From src/api/routes/reporting.py, it is ../templates.

# Actually, careful with templates path.
# server.py: src/api/server.py -> src/api/templates
# reporting.py: src/api/routes/reporting.py -> we need src/api/templates
# So os.path.dirname(os.path.dirname(__file__)) is src/api/routes/.. -> src/api. Correct.

@router.get("/report/{invoice_no}", response_class=HTMLResponse)
async def get_report(
    request: Request, 
    invoice_no: str, 
    user_email: str = Depends(get_current_user_email),
    role: str = Depends(get_current_user_role)
):
    driver = get_db_driver()
    if not driver:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Database unavailable"})

    shop_id = tenant_id_ctx.get()
    data = get_invoice_details(driver, invoice_no, shop_id, shop_id, role=role)
        
    if not data:
        return templates.TemplateResponse("error.html", {"request": request, "message": f"Invoice {invoice_no} not found or access denied."})

    return templates.TemplateResponse("report.html", {
        "request": request,
        "invoice": data["invoice"],
        "line_items": data["line_items"]
    })

@router.get("/activity-log")
async def read_activity_log(
    user_email: str = Depends(get_current_user_email),
    role: str = Depends(get_current_user_role)
):
    driver = get_db_driver()
    if not driver:
        return [] 
    try:
        shop_id = tenant_id_ctx.get()
        data = get_activity_log(driver, shop_id, shop_id, role=role)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch activity log: {e}")
        return []

@router.get("/history")
async def read_history(
    user_email: str = Depends(get_current_user_email),
    role: str = Depends(get_current_user_role)
):
    driver = get_db_driver()
    if not driver:
        return []
    try:
        shop_id = tenant_id_ctx.get()
        data = get_grouped_invoice_history(driver, shop_id, shop_id, role=role)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []
