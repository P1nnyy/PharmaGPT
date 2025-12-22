from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import io
from pydantic import BaseModel
# Revisit imports to ensure no circular deps. ConfirmInvoiceRequest is defined in invoices.py but needed here?
# Actually export-excel expects the FULL payload (invoice_data + normalized_items) to generate Excel.
# So we can redefine the model or import it.
# It's better to verify if `ConfirmInvoiceRequest` is generic enough.
# Let's import it from invoices or redefine. Redefining avoids tight coupling.

from src.database import get_inventory_aggregation
from src.database.connection import get_driver
from src.services.export_service import generate_excel
from src.utils.logging_config import get_logger

logger = get_logger("api.inventory")
router = APIRouter()

class ExportRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

@router.get("/inventory", response_model=List[Dict[str, Any]])
async def get_inventory_endpoint():
    """
    Returns aggregated inventory (Product Name + MRP).
    """
    driver = get_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        return get_inventory_aggregation(driver)
    except Exception as e:
        logger.error(f"Inventory Fetch Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-excel")
async def export_excel_endpoint(request: ExportRequest):
    """
    Generates an Excel report for the current data.
    """
    try:
        excel_bytes = generate_excel(request.invoice_data, request.normalized_items)
        
        invoice_no = request.invoice_data.get("Invoice_No", "Unknown")
        filename = f"Invoice_{invoice_no}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Excel Export Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
