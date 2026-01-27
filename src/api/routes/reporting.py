from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from src.services.database import get_db_driver
from src.api.routes.auth import get_current_user_email
from src.utils.logging_config import get_logger
from src.domain.persistence import (
    get_activity_log,
    get_grouped_invoice_history
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
async def get_report(request: Request, invoice_no: str, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Database unavailable"})

    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:REFERENCES]->(p:Product)
    RETURN i, collect({line: l, product: p, raw_desc: l.raw_description, stated_net: l.stated_net_amount, batch_no: l.batch_no, hsn_code: l.hsn_code}) as items
    """
    
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no, user_email=user_email).single()
    
    if not result:
        return templates.TemplateResponse("error.html", {"request": request, "message": f"Invoice {invoice_no} not found"})

    invoice_node = result["i"]
    items = result["items"]
    
    # Format data for template
    invoice_details = dict(invoice_node)
    line_items = []
    for item in items:
        line_data = dict(item["line"]) if item["line"] else {}
        product_data = dict(item["product"]) if item["product"] else {}
        
        # Safe access for optional raw fields
        raw_desc = item.get("raw_desc", "N/A")
        stated_net = item.get("stated_net", 0.0)
        batch_no = item.get("batch_no", "")
        hsn_code = item.get("hsn_code", "")
        
        line_items.append({
            **line_data, 
            "product_name": product_data.get("name", "Unknown"),
            "raw_product_name": raw_desc,
            "stated_net_amount": stated_net,
            "calculated_tax_amount": line_data.get("calculated_tax_amount", 0.0),
            "batch_no": batch_no,
            "hsn_code": hsn_code
        })

    return templates.TemplateResponse("report.html", {
        "request": request,
        "invoice": invoice_details,
        "line_items": line_items
    })

@router.get("/activity-log")
async def read_activity_log(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return [] 
    try:
        data = get_activity_log(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch activity log: {e}")
        return []

@router.get("/history")
async def read_history(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return []
    try:
        data = get_grouped_invoice_history(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []
