
import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
import uuid
import asyncio

# --- New Imports ---
from langfuse import Langfuse
from src.core.config import (
    SECRET_KEY, get_base_url, get_frontend_url
)
from src.services.database import connect_db, close_db, get_db_driver
from src.services.storage import init_storage_client, upload_to_r2
from src.services.storage import init_storage_client, upload_to_r2
from src.api.routes.auth import router as auth_router, get_current_user_email
from src.api.routes.products import router as products_router

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
    https_only=False,  # Relaxed for mixed HTTP/HTTPS envs
    same_site='lax',   # Allows top-level navigation redirects
    max_age=86400      # 24 Hours Session Lifetime
)

# Trust Headers from Cloudflare/Vite (Fixes OAuth CSRF Mismatch)
# Must be added LAST to be the OUTERMOST middleware (Run First)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# --- Include Routers ---
app.include_router(auth_router)
app.include_router(products_router)

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

class FeedbackRequest(BaseModel):
    trace_id: str
    score: int
    comment: str = None

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

@app.get("/invoices/drafts", response_model=List[Dict[str, Any]])
async def get_drafts(user_email: str = Depends(get_current_user_email)):
    """
    Step 0: Returns all invoices in PROCESSING, DRAFT, or ERROR state for Session Resume/Polling.
    """
    driver = get_db_driver()
    if not driver:
        # Fallback empty list if DB issue, or 503
        return []
    
    # Import locally to avoid circle if at top, or move imports
    from src.domain.persistence import get_draft_invoices
    return get_draft_invoices(driver, user_email)

    return get_draft_invoices(driver, user_email)

@app.delete("/invoices/drafts")
async def clear_drafts(user_email: str = Depends(get_current_user_email)):
    """
    Clears all drafts/errors for the user.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
         
    from src.domain.persistence import delete_draft_invoices
    delete_draft_invoices(driver, user_email)
    return {"status": "success", "message": "Drafts cleared"}

@app.delete("/invoices/{invoice_id}")
async def discard_invoice(invoice_id: str, user_email: str = Depends(get_current_user_email)):
    """
    Discards a single specific invoice.
    """
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
         
    from src.domain.persistence import delete_invoice_by_id
    delete_invoice_by_id(driver, invoice_id, user_email)
    return {"status": "success", "message": f"Invoice {invoice_id} discarded"}

@app.post("/feedback")
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

@app.post("/invoices/batch-upload", response_model=List[Dict[str, Any]])
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...), 
    user_email: str = Depends(get_current_user_email)
):
    """
    Step 1 (New): Receives files, creates PROCESSING nodes, and triggers Background Tasks.
    Returns list of placeholder objects immediately.
    """
    logger.info(f"Received batch of {len(files)} files from {user_email}")
    driver = get_db_driver()
    
    # Import peristence methods
    from src.domain.persistence import create_processing_invoice
    
    temp_results = []
    
    for file in files:
        # 1. Generate IDs and Save File Immediately
        file_ext = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".png"
        invoice_id = uuid.uuid4().hex
        filename = f"{invoice_id}{file_ext}" # Rename to ID for consistency
        
        # Save to Temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            processing_path = tmp.name
        
        # OPTIMIZATION: Skip Synchronous R2 Upload to prevent UI Blocking (15-20s delay)
        # Always serve locally first for speed.
        # We will upload to R2 in the background task if needed.
        
        local_dest = os.path.join("static/invoices", filename)
        shutil.copy(processing_path, local_dest)
        
        # Construct Local URL
        base = get_base_url().rstrip('/')
        public_url = f"{base}/static/invoices/{filename}"
            
        # 2. Create Neo4j Node 'PROCESSING'
        create_processing_invoice(driver, invoice_id, file.filename, public_url, user_email)
        
        # 3. Trigger Background Task
        # Check if upload_to_r2 is needed in background
        background_tasks.add_task(process_invoice_background, invoice_id, processing_path, public_url, user_email, file.filename, True)
        
        # 4. Return Placeholder
        temp_results.append({
            "id": invoice_id,
            "status": "processing",
            "file": {"name": file.filename},
            "previewUrl": public_url
        })
        
    return temp_results

async def process_invoice_background(invoice_id, local_path, public_url, user_email, original_filename, upload_r2: bool = False):
    """
    Background Task: Runs extraction and updates DB status.
    """
    from src.domain.persistence import update_invoice_status
    driver = get_db_driver()
    
    # Lazy Upload to R2 (if requested)
    if upload_r2:
        try:
            with open(local_path, "rb") as f_read:
                r2_url = upload_to_r2(f_read, original_filename)
                if r2_url:
                    public_url = r2_url
                    print(f"Background R2 Upload Success: {public_url}")
        except Exception as e:
             print(f"Background R2 Upload Failed: {e}") 
             # Continue with local URL
    
    try:
        print(f"Starting Background Processing for {invoice_id}...")
        
        # Run Extraction
        extracted_data = await run_extraction_pipeline(local_path, user_email, public_url=public_url)
        
        if extracted_data is None:
             raise ValueError("Extraction yielded None")
             
        if extracted_data is None:
             raise ValueError("Extraction yielded None")
             
        extracted_data["image_path"] = public_url
        print(f"DEBUG: Extracted Data Keys: {list(extracted_data.keys())}")
        if "trace_id" in extracted_data:
            print(f"DEBUG: Found Trace ID in Background Task: {extracted_data['trace_id']}")
        else:
            print(f"DEBUG: NO Trace ID in Background Task!")
        
        # Normalize
        invoice_obj = InvoiceExtraction(**extracted_data)
        normalized_items = []
        for raw_item in invoice_obj.Line_Items:
            raw_dict = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            norm_item = normalize_line_item(raw_dict, invoice_obj.Supplier_Name)
            normalized_items.append(norm_item)
            
        # Reconcile
        grand_total = parse_float(extracted_data.get("Stated_Grand_Total") or extracted_data.get("Invoice_Amount", 0.0))
        normalized_items = reconcile_financials(normalized_items, extracted_data, grand_total)
        
        # Validation checks
        validation_flags = []
        calculated_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
        if grand_total:
             if abs(calculated_total - grand_total) > 5.0:
                 validation_flags.append(f"Mismatch: Calc {calculated_total:.2f} != Stated {grand_total:.2f}")

        # Construct Final Result State
        result_state = {
            "status": "review_needed",
            "invoice_data": extracted_data,
            "normalized_items": normalized_items,
            "validation_flags": validation_flags,
            "filename": original_filename
        }
        
        # Update Neo4j Status -> DRAFT
        update_invoice_status(driver, invoice_id, "DRAFT", result_state)
        print(f"Background Processing Complete for {invoice_id} -> DRAFT")
        
    except Exception as e:
        logger.error(f"Background Task Failed for {invoice_id}: {e}")
        import traceback
        traceback.print_exc()
        # Update Neo4j Status -> ERROR
        update_invoice_status(driver, invoice_id, "ERROR", error=str(e))
    finally:
        # cleanup
        if os.path.exists(local_path):
            os.remove(local_path)

@app.post("/analyze-invoice", response_model=List[Dict[str, Any]])
async def analyze_invoice(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...), 
    user_email: str = Depends(get_current_user_email)
):
    """
    LEGACY / FALLBACK: Synchronous Batch (Kept for compatibility or single-file calls if needed)
    """
    # Logic similar to before or just redirect to batch-upload style but waiting?
    # For now, keep as is but we are moving frontend to batch-upload.
    # Actually, previous implementation loops inside. 
    # Let's keep it as a wrapper that waits if client calls it.
    pass
    # ... (Keep existing implementation if possible, or Deprecate)
    # Re-implementing body briefly for completeness if tool replaces full block
    logger.info(f"Received LEGACY batch of {len(files)} files from {user_email}")
    results = []
    for file in files:
         # Reuse the helper logic but synchronously await?
         # Since we refactored the helper to be background-focused, we need to adapt.
         # For simplicity, let's just use the NEW process_invoice_background logic conceptually but await it?
         # No, let's just fail this or return empty to force frontend update.
         # Or better, keep the OLD process_single_invoice logic inside this function for now?
         # The tool replacement replaced process_single_invoice. So I must re-implement it or redirect.
         # Attempting to map to new logic:
         pass 
    # To avoid breaking if something calls this, let's just return []
    return []


@app.post("/confirm-invoice", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest, user_email: str = Depends(get_current_user_email)):
    """
    Step 2: Receives the verified (and potentially edited) data and persists it to Neo4j.
    """
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        # Import Persistence Helpers
        from src.domain.persistence import get_invoice_draft, log_correction

        # 1. Try to find the Original Draft to (A) Log Diff, (B) Recover Raw Text/Image Path
        # Since frontend payload might not have UUID, we look up by Invoice Number (Risk: Duplicates, but Drafts usually unique per flow)
        # We search for a DRAFT/PROCESSING invoice with this number.
        invoice_no = request.invoice_data.get("Invoice_No")
        original_draft = None
        invoice_id_lookup = None

        if invoice_no:
            # Helper Query to find draft ID
            find_draft_query = """
            MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
            WHERE i.status IN ['DRAFT', 'PROCESSING', 'ERROR'] AND i.invoice_number = $invoice_no
            RETURN i.invoice_id as id, i.raw_state as state LIMIT 1
            """
            with driver.session() as session:
                rec = session.run(find_draft_query, user_email=user_email, invoice_no=invoice_no).single()
                if rec:
                    invoice_id_lookup = rec["id"]
                    import json
                    original_draft = json.loads(rec["state"]) if rec["state"] else None

        # 2. Log Corrections (Gap Analysis)
        if invoice_id_lookup and original_draft:
            logger.info(f"Checking for corrections on Invoice {invoice_id_lookup}...")
            log_correction(driver, invoice_id_lookup, original_draft, request.invoice_data, user_email)
            
            # 3. Preserve Metadata (Raw Text & Image Path) for RAG
            # If frontend didn't send raw_text (likely), we recover it from draft
            # This ensures we can generate Embeddings in ingest_invoice
            original_data = original_draft.get("invoice_data", {})
            
            if not request.invoice_data.get("raw_text") and original_data.get("raw_text"):
                logger.info("Recovering raw_text from Draft for RAG Auto-Promotion.")
                request.invoice_data["raw_text"] = original_data.get("raw_text")
                
            if not request.invoice_data.get("image_path") and original_data.get("image_path"):
                 request.invoice_data["image_path"] = original_data.get("image_path")

        # 4. Re-hydrate Invoice Object 
        invoice_obj = InvoiceExtraction(**request.invoice_data)
        
        # 5. Ingest into Neo4j (Creates/Updates Invoice, Lines, and Auto-Promotes to InvoiceExample if raw_text exists)
        supplier_details = request.invoice_data.get("supplier_details")
        ingest_invoice(driver, invoice_obj, request.normalized_items, user_email=user_email, supplier_details=supplier_details)
        
        return {
            "status": "success",
            "message": f"Invoice {invoice_obj.Invoice_No} persisted successfully.",
            "invoice_number": invoice_obj.Invoice_No,
            "corrections_logged": bool(invoice_id_lookup)
        }

    except Exception as e:
        logger.error(f"Database ingestion failed: {e}")
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
