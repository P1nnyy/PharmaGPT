from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, List
import tempfile
import shutil
import os
import uuid
from src.schemas import InvoiceExtraction
from src.normalization import normalize_line_item, reconcile_financials, parse_float
from src.database import ingest_invoice, check_inflation_on_analysis, get_recent_activity
from src.database.connection import get_driver 
from src.workflow.graph import run_extraction_pipeline
from src.utils.logging_config import get_logger
from pydantic import BaseModel

logger = get_logger("api.invoices")
router = APIRouter()

# Template Setup (Assuming templates dir is in src/api/templates)
# Adjust path relative to this file: src/api/routes/invoices.py -> ../templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"))

class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]
    image_path: str = None

@router.post("/analyze-invoice", response_model=Dict[str, Any])
async def analyze_invoice(file: UploadFile = File(...)):
    """
    Step 1: Analyzes the invoice (OCR + Normalization) but DOES NOT persist to DB.
    """
    tmp_path = None
    saved_image_path = None
    try:
        suffix = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".tmp"
        
        # 1. Save temporarily for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        # 2. Save Permanently for History
        file.file.seek(0)
        unique_filename = f"{uuid.uuid4()}{suffix}"
        permanent_path = os.path.join("uploads", "invoices", unique_filename)
        with open(permanent_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Store relative path for frontend access (via /static mount)
        saved_image_path = f"/static/invoices/{unique_filename}"
        
        extracted_data = await run_extraction_pipeline(tmp_path)
        if extracted_data is None:
            raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
            
        # SANITIZATION (Prevent Pydantic Crash on Missing Data)
        # Ensure all line items have a valid Product string.
        if "Line_Items" in extracted_data:
            valid_items = []
            for item in extracted_data["Line_Items"]:
                if not item: continue
                # Fix missing Product
                if not item.get("Product"):
                    item["Product"] = "Unknown Item (Missing Name)"
                
                # Ensure fields are compatible (handle None explicitly if needed)
                valid_items.append(item)
            extracted_data["Line_Items"] = valid_items
        
        invoice_obj = InvoiceExtraction(**extracted_data)
        normalized_items = []
        for raw_item in invoice_obj.Line_Items:
            raw_dict = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            norm_item = normalize_line_item(raw_dict, invoice_obj.Supplier_Name)
            normalized_items.append(norm_item)
        
        grand_total = parse_float(extracted_data.get("Stated_Grand_Total") or extracted_data.get("Invoice_Amount", 0.0))
        normalized_items = reconcile_financials(normalized_items, extracted_data, grand_total)
        
        driver = get_driver()
        if driver:
             normalized_items = check_inflation_on_analysis(driver, normalized_items)
        
        validation_flags = []
        calculated_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
        if grand_total > 0 and abs(calculated_total - grand_total) > 5.0:
             validation_flags.append(f"Critical Mismatch: Calculated ({calculated_total}) != Stated ({grand_total})")

        return {
            "status": "review_needed",
            "message": "Analysis complete.",
            "invoice_data": extracted_data,
            "normalized_items": normalized_items,
            "validation_flags": validation_flags,
            "image_path": saved_image_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analysis Failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/confirm-invoice", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest):
    """
    Step 2: Persists validated data to Neo4j.
    """
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        invoice_obj = InvoiceExtraction(**request.invoice_data)
        ingest_invoice(driver, invoice_obj, request.normalized_items, request.image_path)
        
        return {
            "status": "success",
            "message": f"Invoice {invoice_obj.Invoice_No} persisted successfully.",
            "invoice_number": invoice_obj.Invoice_No
        }
    except Exception as e:
        logger.exception("Confirmation Failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report/{invoice_no}", response_class=HTMLResponse)
async def get_report(request: Request, invoice_no: str):
    driver = get_driver()
    if not driver:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Database unavailable"})

    query = """
    MATCH (i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:REFERENCES]->(p:Product)
    RETURN i, collect({line: l, product: p, raw_desc: l.raw_description, stated_net: l.stated_net_amount, batch_no: l.batch_no, hsn_code: l.hsn_code}) as items
    """
    
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no).single()
    
    if not result:
        return templates.TemplateResponse("error.html", {"request": request, "message": f"Invoice {invoice_no} not found"})

    invoice_node = result["i"]
    items = result["items"]
    
    invoice_details = dict(invoice_node)
    line_items = []
    for item in items:
        line_data = dict(item["line"]) if item["line"] else {}
        product_data = dict(item["product"]) if item["product"] else {}
        
        line_items.append({
            **line_data, 
            "product_name": product_data.get("name", "Unknown"),
            "raw_product_name": item.get("raw_desc", "N/A"),
            "stated_net_amount": item.get("stated_net", 0.0),
            "calculated_tax_amount": line_data.get("calculated_tax_amount", 0.0),
            "batch_no": item.get("batch_no", ""),
            "hsn_code": item.get("hsn_code", "")
        })

    return templates.TemplateResponse("report.html", {
        "request": request,
        "invoice": invoice_details,
        "line_items": line_items
    })

@router.get("/invoices/{invoice_no}/items", response_model=Dict[str, Any])
async def get_invoice_items_json(invoice_no: str):
    """
    Returns invoice details and line items as JSON (for Frontend Modal).
    """
    driver = get_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")

    query = """
    MATCH (i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:REFERENCES]->(p:Product)
    RETURN i, collect({line: l, product: p, raw_desc: l.raw_description, stated_net: l.stated_net_amount, batch_no: l.batch_no, hsn_code: l.hsn_code}) as items
    """
    
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no).single()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_no} not found")

    invoice_node = result["i"]
    items = result["items"]
    
    invoice_details = dict(invoice_node)
    line_items = []
    for item in items:
        if not item["line"]: continue
        
        line_data = dict(item["line"])
        product_data = dict(item["product"]) if item["product"] else {}
        
        line_items.append({
            **line_data, 
            "product_name": product_data.get("name", "Unknown"),
            "raw_product_name": item.get("raw_desc", "N/A"),
            "stated_net_amount": item.get("stated_net", 0.0),
            "calculated_tax_amount": line_data.get("calculated_tax_amount", 0.0),
            "batch_no": item.get("batch_no", ""),
            "hsn_code": item.get("hsn_code", "")
        })

    return {
        "invoice": invoice_details,
        "line_items": line_items
    }

@router.get("/activity-log", response_model=List[Dict[str, Any]])
async def get_activity_log():
    """
    Returns a flat list of recent invoice activity for the Timeline View.
    """
    driver = get_driver()
    if not driver:
        # Fallback for UI if DB is down
        return []

    try:
        activity = get_recent_activity(driver)
        return activity
    except Exception as e:
        logger.error(f"Failed to fetch activity log: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activity log")
