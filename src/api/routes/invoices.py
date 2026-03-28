from typing import List, Dict, Any
import uuid
import shutil
import tempfile
import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from src.services.database import get_db_driver
import asyncio
import json
from src.services.storage import upload_to_r2
from src.services.tasks import process_invoice_background, enrich_invoice_items_background
from src.api.routes.auth import get_current_user_email, get_current_user_role
from src.utils.logging_config import get_logger, tenant_id_ctx
from src.services.task_manager import manager as task_manager
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
    log_correction,
    index_invoice_for_rag
)
from src.workflow.graph import run_supply_chain_intelligence
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/invoices", tags=["invoices"])

class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

@router.get("/drafts", response_model=List[Dict[str, Any]])
async def get_drafts(
    user_email: str = Depends(get_current_user_email),
    role: str = Depends(get_current_user_role)
):
    driver = get_db_driver()
    if not driver:
        return []
    tenant_id = tenant_id_ctx.get()
    return get_draft_invoices(driver, user_email, tenant_id, role=role)

@router.delete("/drafts")
async def clear_drafts(user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    
    # 1. Kill any active background scans for this user
    task_manager.cancel_all(user_email)
    
    # 2. Cleanup Database
    tenant_id = tenant_id_ctx.get()
    delete_draft_invoices(driver, user_email, tenant_id)
    return {"status": "success", "message": "Drafts cleared and active scans cancelled"}
@router.delete("/{invoice_id}")
async def discard_invoice(invoice_id: str, wipe: bool = False, user_email: str = Depends(get_current_user_email), role: str = Depends(get_current_user_role)):
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    
    # 1. Cancel active scan task if it exists
    task_manager.cancel(user_email, invoice_id)
    
    # 2. Delete from DB
    is_admin = (role == "Admin")
    tenant_id = tenant_id_ctx.get()
    delete_invoice_by_id(driver, invoice_id, user_email, tenant_id, wipe=wipe, is_admin=is_admin)
    return {"status": "success", "message": f"Invoice {invoice_id} {'wiped' if wipe else 'discarded'} and scan cancelled"}

@router.get("/stream-status")
async def stream_status(
    token: str = None,
    db=Depends(get_db_driver)
):
    """
    SSE endpoint to push status updates to the frontend.
    Manually validates token from query string as EventSource doesn't support headers.
    """
    from src.core.config import SECRET_KEY, ALGORITHM
    from jose import jwt, JWTError

    if not token:
        logger.warning("SSE connection attempt without token")
        raise HTTPException(status_code=401, detail="Token missing")

    try:
        # Debug logging for token presence
        if token:
            logger.info(f"SSE Auth attempting with token suffix: ...{token[-8:]}")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        if not email:
            logger.error(f"SSE Auth: Token decoded but 'sub' missing. Payload keys: {list(payload.keys())}")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_email = email
        
        # Fallback for missing tenant_id in token
        if not tenant_id or tenant_id == "anonymous":
            from src.api.routes.auth import resolve_user_tenant
            tenant_id = await resolve_user_tenant(user_email)
            logger.info(f"SSE Auth: Resolved missing tenant_id from DB for user: {user_email} -> {tenant_id}")

        logger.info(f"SSE Auth Successful for user: {user_email}, tenant: {tenant_id}")
    except JWTError as e:
        logger.error(f"SSE JWT Validation Failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    # Fetch role for SSE context
    from src.api.routes.auth import get_current_user_role
    role = await get_current_user_role(user_email)

    async def event_generator():
        last_state_hash = None
        heartbeat_count = 0
        while True:
            try:
                drafts = get_draft_invoices(db, user_email, tenant_id, role=role)
                # Create a simple hash of IDs and statuses to detect changes
                current_state = [(d['id'], d.get('status')) for d in drafts]
                current_hash = hash(tuple(current_state))
                
                if current_hash != last_state_hash:
                    yield f"data: {json.dumps({'type': 'update', 'drafts': drafts})}\n\n"
                    last_state_hash = current_hash
                    heartbeat_count = 0
                else:
                    heartbeat_count += 1
                    # Send heartbeat every 15 iterations (~30 seconds)
                    if heartbeat_count >= 15:
                        yield ": heartbeat\n\n"
                        heartbeat_count = 0
                
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"SSE Stream Error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Internal stream error'})}\n\n"
                break
                
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/{invoice_number}/items")
async def read_invoice_items(
    invoice_number: str, 
    user_email: str = Depends(get_current_user_email),
    role: str = Depends(get_current_user_role)
):
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    try:
        tenant_id = tenant_id_ctx.get()
        data = get_invoice_details(driver, invoice_number, user_email=user_email, tenant_id=tenant_id, role=role)
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
    temp_ids: List[str] = Form(None),
    user_email: str = Depends(get_current_user_email)
):
    logger.info(f"Received batch of {len(files)} files from {user_email}")
    driver = get_db_driver()
    temp_results = []
    
    for i, file in enumerate(files):
        file_ext = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".png"
        invoice_id = uuid.uuid4().hex
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            # Offload blocking IO to a thread
            await asyncio.to_thread(shutil.copyfileobj, file.file, tmp)
            processing_path = tmp.name
        
        # Create DB entry first with tenant context
        tenant_id = tenant_id_ctx.get()
        create_processing_invoice(driver, invoice_id, file.filename, None, user_email, tenant_id)
        
        # Use background_tasks for safer execution and proper context management
        background_tasks.add_task(
            process_invoice_background, invoice_id, processing_path, None, user_email, tenant_id, file.filename
        )
        # Registration now happens INSIDE the background task for synchronization
        
        result = {
            "id": invoice_id,
            "status": "processing",
            "file": {"name": file.filename},
            "previewUrl": None
        }
        if temp_ids and i < len(temp_ids):
            result["temp_id"] = temp_ids[i]
            
        temp_results.append(result)
        
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
async def confirm_invoice(request: ConfirmInvoiceRequest, background_tasks: BackgroundTasks, user_email: str = Depends(get_current_user_email)):
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        invoice_no = request.invoice_data.get("Invoice_No")
        draft_id = request.invoice_data.get("id") or request.invoice_data.get("invoice_id")
        original_draft = None
        invoice_id_lookup = draft_id

        if invoice_no and not draft_id:
            # Legacy/Fallback: Try to find by number if ID is missing
            find_draft_query = """
            MATCH (u:User {email: $user_email})
            OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
            WITH u, s
            
            MATCH (i:Invoice {tenant_id: $tenant_id})
            WHERE i.status IN ['DRAFT', 'PROCESSING', 'ERROR'] 
              AND i.invoice_number = $invoice_no
            RETURN i.invoice_id as id, i.raw_state as state LIMIT 1
            """
            with driver.session() as session:
                def _find_draft(tx):
                    tenant_id = tenant_id_ctx.get()
                    rec = tx.run(find_draft_query, user_email=user_email, tenant_id=tenant_id, invoice_no=invoice_no).single()
                    if rec:
                        return rec["id"], json.loads(rec["state"]) if rec["state"] else None
                    return None, None

                invoice_id_lookup, original_draft = session.execute_read(_find_draft)

        if invoice_id_lookup and not original_draft:
            # Fetch draft data if we only have the ID
            fetch_query = """
            MATCH (u:User {email: $user_email})
            OPTIONAL MATCH (u)-[:OWNS_SHOP|WORKS_AT]->(s:Shop)
            WITH u, s
            
            MATCH (i:Invoice {invoice_id: $id, tenant_id: $tenant_id})
            RETURN i.raw_state as state
            """
            with driver.session() as session:
                def _fetch_state(tx):
                    tenant_id = tenant_id_ctx.get()
                    res = tx.run(fetch_query, user_email=user_email, id=invoice_id_lookup, tenant_id=tenant_id).single()
                    return res["state"] if res else None
                state_str = session.execute_read(_fetch_state)
                if state_str:
                    original_draft = json.loads(state_str)

        if invoice_id_lookup and original_draft:
            logger.info(f"Checking for corrections on Invoice {invoice_id_lookup}...")
            log_correction(driver, invoice_id_lookup, original_draft, request.invoice_data, user_email)
            
            original_data = original_draft.get("invoice_data", {})
            if not request.invoice_data.get("raw_text") and original_data.get("raw_text"):
                request.invoice_data["raw_text"] = original_data.get("raw_text")
            if not request.invoice_data.get("image_path") and original_data.get("image_path"):
                 request.invoice_data["image_path"] = original_data.get("image_path")

        if not invoice_id_lookup:
            raise HTTPException(status_code=400, detail="Missing Invoice ID (draft_id) for confirmation")

        invoice_obj = InvoiceExtraction(**request.invoice_data)
        supplier_details = request.invoice_data.get("supplier_details")
        
        # Use invoice_id_lookup to update the EXACT node that was previously in draft/processing status
        tenant_id = tenant_id_ctx.get()
        ingest_invoice(driver, invoice_id_lookup, invoice_obj, request.normalized_items, user_email=user_email, tenant_id=tenant_id, supplier_details=supplier_details)
        
        logger.info(f"Confirmed Invoice {invoice_obj.Invoice_No}. ID: {invoice_id_lookup}")
        
        # Note: No need for delete_redundant_draft because ingest_invoice now 
        # overwrites the draft node directly using its invoice_id.
        
        
        # Trigger Automated Enrichment and RAG Indexing in background
        tenant_id = tenant_id_ctx.get()
        background_tasks.add_task(enrich_invoice_items_background, request.normalized_items, user_email, tenant_id)
        background_tasks.add_task(index_invoice_for_rag, driver, invoice_obj)
        background_tasks.add_task(run_supply_chain_intelligence, tenant_id, user_email)

        return {
            "status": "success",
            "message": f"Invoice {invoice_obj.Invoice_No} persisted successfully.",
            "invoice_number": invoice_obj.Invoice_No,
            "corrections_logged": bool(invoice_id_lookup)
        }

    except Exception as e:
        logger.error(f"Database ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
