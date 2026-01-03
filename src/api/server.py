
import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
import uuid

# --- New Imports ---
from src.core.config import (
    SECRET_KEY, get_base_url, get_frontend_url
)
from src.services.database import connect_db, close_db, get_db_driver
from src.services.storage import init_storage_client, upload_to_r2
from src.api.routes.auth import router as auth_router, get_current_user_email

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import uvicorn

from src.utils.logging_config import setup_logging, get_logger, request_id_ctx
from src.domain.schemas import InvoiceExtraction
from src.domain.normalization import normalize_line_item, parse_float, reconcile_financials
from src.domain.persistence import ingest_invoice, get_activity_log, get_inventory, get_invoice_details, get_grouped_invoice_history
from src.workflow.graph import run_extraction_pipeline

# --- Logging Configuration ---
# 1. Setup Enterprise Logging using config
setup_logging(log_dir="logs", log_file="app.log")
logger = get_logger("api")

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Invoice Extractor API")

# ProxyHeadersMiddleware moved to bottom to ensure it runs first


# Mount Static Directory
os.makedirs("static/invoices", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Middleware ---
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    Generates a unique Request ID for every request.
    Injects it into ContextVar for logging.
    Returns X-Request-ID header.
    """
    req_id = str(uuid.uuid4())
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as e:
        # If middleware itself fails (rare), we still want to log it
        logger.exception("Middleware Error")
        raise e
    finally:
        request_id_ctx.reset(token)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches all unhandled exceptions.
    Logs full traceback with Request ID.
    Returns JSON to frontend.
    """
    req_id = request_id_ctx.get()
    logger.exception(f"Unhandled Exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal Server Error", 
            "detail": str(exc),
            "request_id": req_id
        }
    )

# --- CORS Middleware ---
origins = [
    "http://localhost:5173",  # Vite Default
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# --- Session Middleware ---
# Dynamic Security Configuration
current_base_url = get_base_url()

app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY, 
    https_only=True,   # Strictly enforce HTTPS
    same_site='lax',   # Better for OAuth redirects
    max_age=86400      # 24 Hours Session Lifetime
)

# Trust Headers from Cloudflare/Vite (Fixes OAuth CSRF Mismatch)
# Must be added LAST to be the OUTERMOST middleware (Run First)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# --- Include Routers ---
app.include_router(auth_router)

# --- Startup / Shutdown ---
@app.on_event("startup")
def startup_event():
    connect_db() # Connects to Neo4j and inits vector index
    init_storage_client() # Inits S3/R2

@app.on_event("shutdown")
def shutdown_event():
    close_db()

# --- Request Models ---
from pydantic import BaseModel
class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

# --- API Endpoints (Core Logic) ---
# Note: Ideally these should move to src/api/routes/invoices.py etc.

@app.get("/logs")
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

@app.post("/analyze-invoice", response_model=Dict[str, Any])
async def analyze_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    user_email: str = Depends(get_current_user_email)
):
    """
    Step 1: Analyzes the invoice (OCR + Normalization) but DOES NOT persist to DB.
    Returns the raw and normalized data for frontend verification.
    """
    processing_path = None
    public_url = None
    
    try:
        print(f"Received file: {file.filename} from {user_email}")
        
        file_ext = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".png"
        file_id = uuid.uuid4().hex
        filename = f"{file_id}{file_ext}"
        
        # 1. Save to Temporary File for Processing (Gemini needs local file)
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            processing_path = tmp.name
            
        print(f"Saved temp invoice to: {processing_path}")
        
        # 2. Upload to R2 (Cloud Storage) for Frontend/History
        with open(processing_path, "rb") as f_read:
            public_url = upload_to_r2(f_read, filename)
            
        if public_url:
            print(f"Uploaded to R2: {public_url}")
        else:
            print("R2 Upload Failed or Not Configured. Image might not persist.")
            
        # Schedule cleanup of temp file
        background_tasks.add_task(os.remove, processing_path)
            
    except Exception as e:
         if processing_path and os.path.exists(processing_path):
             os.remove(processing_path)
         raise HTTPException(status_code=500, detail=f"File processing failed: {str(e)}")

    # Scope 2: Extraction
    try:
        # 2. Extract Data using Gemini Vision + Agents (LangGraph)
        print("Starting extraction pipeline...")
        
        # PASS LOCAL PATH (For Vision) AND PUBLIC URL (For State/DB)
        extracted_data = await run_extraction_pipeline(processing_path, user_email, public_url=public_url)
        print("Extraction pipeline completed.")
        
        if extracted_data is None:
            raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
            
        # INJECT IMAGE PATH INTO EXTRACTED DATA
        # Ensure the frontend receives the persistent URL
        extracted_data["image_path"] = public_url or processing_path # Fallback to local path if R2 fails (will likely break frontend but better than null)
        
        # 3. Normalize Line Items
        # Hydrate into Pydantic model
        invoice_obj = InvoiceExtraction(**extracted_data)
        
        normalized_items = []
        for raw_item in invoice_obj.Line_Items:
            # Conversion: Normalization now expects a dict, but we have a Pydantic model
            raw_dict = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            norm_item = normalize_line_item(raw_dict, invoice_obj.Supplier_Name)
            normalized_items.append(norm_item)
        
        # 3.b Apply Global Proration (Phase 3)
        # 3.b Apply Global Proration (Phase 3) - Smart Directional Reconciliation
        # This logic ensures we only Apply Modifiers if they mathematically CLOSE the gap.
        # It handles "Double Tax" (Inflation) and "Missing Discount" (Deflation) automatically.
        
        # FIX: Use 'Stated_Grand_Total' from schema
        grand_total = parse_float(extracted_data.get("Stated_Grand_Total") or extracted_data.get("Invoice_Amount", 0.0))
        
        # Pass the full data dict as modifiers source (contains Global_Discount_Amount, etc.)
        normalized_items = reconcile_financials(normalized_items, extracted_data, grand_total)
        
        # 4. Financial Integrity Check
        validation_flags = []
        
        # Calculate sum of line items from extracted/normalized data
        calculated_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
        stated_total = extracted_data.get("Stated_Grand_Total")
        
        if stated_total:
            try:
                    stated_val = float(stated_total)
                    # Allow for small rounding differences (e.g. +/- 5.00 for rounding off)
                    if abs(calculated_total - stated_val) > 5.0:
                        validation_flags.append(
                            f"Critical Mismatch: Calculated Total ({calculated_total:.2f}) != Stated Total ({stated_val:.2f}). Rows might be missing!"
                        )
            except ValueError:
                    pass # Stated total might be non-numeric, ignore check
        
        # Return data for Review (No DB persistence yet)
        return {
            "status": "review_needed",
            "message": "Analysis complete. Please review and confirm.",
            "invoice_data": extracted_data, # Return raw extraction as dict (now includes image_path)
            "normalized_items": normalized_items,
            "validation_flags": validation_flags
        }

    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/confirm-invoice", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest, user_email: str = Depends(get_current_user_email)):
    """
    Step 2: Receives the verified (and potentially edited) data and persists it to Neo4j.
    """
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        # 1. Re-hydrate Invoice Object from the (possibly edited) invoice_data
        # Note: If frontend edits invoice header, 'request.invoice_data' should reflect that.
        invoice_obj = InvoiceExtraction(**request.invoice_data)
        
        # 2. Ingest into Neo4j
        # Extract supplier details if available
        supplier_details = request.invoice_data.get("supplier_details")
        
        # We pass the confirmed normalized_items directly
        ingest_invoice(driver, invoice_obj, request.normalized_items, user_email=user_email, supplier_details=supplier_details)
        
        return {
            "status": "success",
            "message": f"Invoice {invoice_obj.Invoice_No} persisted successfully.",
            "invoice_number": invoice_obj.Invoice_No
        }

    except Exception as e:
        logger.error(f"Database ingestion failed: {e}")
        # Traceback is already logged by logger.exception if we use it, keeping traceback for now if needed explicitly but logger.exception is better
        logger.exception("Ingestion Traceback")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/report/{invoice_no}", response_class=HTMLResponse)
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

@app.get("/activity-log")
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

@app.get("/inventory")
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

@app.get("/history")
async def read_history(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return []
    try:
        from src.domain.persistence import get_grouped_invoice_history
        data = get_grouped_invoice_history(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []

@app.get("/invoices/{invoice_number}/items")
async def read_invoice_items(invoice_number: str, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    # Import locally to avoid circular imports if any, or just ensure it's imported at top
    from src.domain.persistence import get_invoice_details
    
    try:
        data = get_invoice_details(driver, invoice_number, user_email=user_email)
        if not data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoice details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=5001, reload=True)
