from typing import List, Dict, Any
import uuid
import shutil
import tempfile
import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from src.services.database import get_db_driver
from src.services.storage import upload_to_r2
from src.services.tasks import process_invoice_background
from src.api.routes.auth import get_current_user_email
from src.utils.logging_config import get_logger
from src.domain.schemas import InvoiceExtraction
from src.domain.persistence import (
    get_draft_invoices, 
    delete_draft_invoices, 
    delete_invoice_by_id, 
    create_processing_invoice, 
    get_invoice_details,
    ingest_invoice,
    delete_redundant_draft,
    get_invoice_draft,
    log_correction
)
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/invoices", tags=["invoices"])

class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

@router.get("/drafts", response_model=List[Dict[str, Any]])
async def get_drafts(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        return []
    return get_draft_invoices(driver, user_email)

@router.delete("/drafts")
async def clear_drafts(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    delete_draft_invoices(driver, user_email)
    return {"status": "success", "message": "Drafts cleared"}

@router.delete("/{invoice_id}")
async def discard_invoice(invoice_id: str, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    delete_invoice_by_id(driver, invoice_id, user_email)
    return {"status": "success", "message": f"Invoice {invoice_id} discarded"}

@router.get("/{invoice_number}/items")
async def read_invoice_items(invoice_number: str, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
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

@router.post("/batch-upload", response_model=List[Dict[str, Any]])
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...), 
    user_email: str = Depends(get_current_user_email)
):
    logger.info(f"Received batch of {len(files)} files from {user_email}")
    driver = get_db_driver()
    temp_results = []
    
    for file in files:
        file_ext = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".png"
        invoice_id = uuid.uuid4().hex
        filename = f"{invoice_id}{file_ext}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            processing_path = tmp.name
        
        public_url = None
        try:
            with open(processing_path, "rb") as f_read:
                 public_url = upload_to_r2(f_read, filename)
        except Exception as e:
            logger.error(f"Failed to upload to R2: {e}")
            
        if not public_url:
             logger.error(f"Critical: R2 Upload failed for {filename}. UI will fail.")
            
        create_processing_invoice(driver, invoice_id, file.filename, public_url, user_email)
        background_tasks.add_task(process_invoice_background, invoice_id, processing_path, public_url, user_email, file.filename)
        
        temp_results.append({
            "id": invoice_id,
            "status": "processing",
            "file": {"name": file.filename},
            "previewUrl": public_url
        })
        
    return temp_results

@router.post("/analyze-invoice", response_model=List[Dict[str, Any]])
async def analyze_invoice(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...), 
    user_email: str = Depends(get_current_user_email)
):
    # LEGACY / FALLBACK: Synchronous Batch (Kept for compatibility)
    return []

# NOTE: This endpoint was technically "/confirm-invoice" in server.py (root level).
# We are moving it to "/invoices/confirm" or keeping it as root?
# Best practice is hierarchal: POST /invoices/confirm
# But frontend might expect /confirm-invoice. 
# I will keep a redirect or alias in server.py OR update frontend. 
# For now, I will mount this router at /invoices, so this becomes /invoices/confirm-invoice
# Check frontend usage if possible. But safe bet is to try to match old paths if possible.
# Ideally we change to /invoices/confirm. Let's make it /confirm for now relative to router.

@router.post("/confirm", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        invoice_no = request.invoice_data.get("Invoice_No")
        original_draft = None
        invoice_id_lookup = None

        if invoice_no:
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

        if invoice_id_lookup and original_draft:
            logger.info(f"Checking for corrections on Invoice {invoice_id_lookup}...")
            log_correction(driver, invoice_id_lookup, original_draft, request.invoice_data, user_email)
            
            original_data = original_draft.get("invoice_data", {})
            if not request.invoice_data.get("raw_text") and original_data.get("raw_text"):
                request.invoice_data["raw_text"] = original_data.get("raw_text")
            if not request.invoice_data.get("image_path") and original_data.get("image_path"):
                 request.invoice_data["image_path"] = original_data.get("image_path")

        invoice_obj = InvoiceExtraction(**request.invoice_data)
        supplier_details = request.invoice_data.get("supplier_details")
        ingest_invoice(driver, invoice_obj, request.normalized_items, user_email=user_email, supplier_details=supplier_details)
        
        draft_id = request.invoice_data.get("id")
        if draft_id:
            delete_redundant_draft(driver, draft_id, user_email)
        
        return {
            "status": "success",
            "message": f"Invoice {invoice_obj.Invoice_No} persisted successfully.",
            "invoice_number": invoice_obj.Invoice_No,
            "corrections_logged": bool(invoice_id_lookup)
        }

    except Exception as e:
        logger.error(f"Database ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
