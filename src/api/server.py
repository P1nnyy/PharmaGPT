import shutil
import tempfile
import sys
import os
import io
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env vars BEFORE imports that might use them
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from src.services.export_service import generate_excel
from neo4j import GraphDatabase
from pydantic import BaseModel
import uvicorn
import uuid
from src.utils.logging_config import setup_logging, get_logger, request_id_ctx
from fastapi.responses import JSONResponse

# --- Logging Configuration ---
# 1. Setup Enterprise Logging using config
setup_logging(log_dir="logs", log_file="app.log")
logger = get_logger("api")

from src.schemas import InvoiceExtraction
from src.normalization import normalize_line_item, parse_float
from src.persistence import ingest_invoice
from src.workflow.graph import run_extraction_pipeline

# Basic validation that API Key exists (optional but good practice)
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    # Fallback to GEMINI_API_KEY for backward compatibility
    API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logger.warning("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables.")

app = FastAPI(title="Invoice Extractor API")

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
    "http://localhost:5173",
    "http://localhost:3000",
    "https://pharmagpt.co",
    "https://api.pharmagpt.co",
    "http://localhost:8000",
    "http://192.168.1.4:5173",  # Mobile LAN
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Neo4j Connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = None

@app.on_event("startup")
def startup_event():
    global driver
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("Connected to Neo4j.")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e} - Application will start in partial mode (No DB)")

@app.on_event("shutdown")
def shutdown_event():
    if driver:
        driver.close()

# --- Request Models ---

class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

# --- API Endpoints ---


        
@app.post("/analyze-invoice", response_model=Dict[str, Any])
async def analyze_invoice(file: UploadFile = File(...)):
    """
    Step 1: Analyzes the invoice (OCR + Normalization) but DOES NOT persist to DB.
    Returns the raw and normalized data for frontend verification.
    """
    tmp_path = None
    try:
        # Scope 1: File Save
        print(f"Received file: {file.filename}")
        suffix = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".tmp"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        print(f"Saved temp file to: {tmp_path}")
        
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # Scope 2: Extraction (Outside the with block)
    try:
        # 2. Extract Data using Gemini Vision + Agents (LangGraph)
        print("Starting extraction pipeline...")
        extracted_data = await run_extraction_pipeline(tmp_path)
        print("Extraction pipeline completed.")
        
        if extracted_data is None:
            raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
        
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
        
        from src.normalization import reconcile_financials
        
        # FIX: Use 'Stated_Grand_Total' from schema
        grand_total = parse_float(extracted_data.get("Stated_Grand_Total") or extracted_data.get("Invoice_Amount", 0.0))
        
        # Pass the full data dict as modifiers source (contains Global_Discount_Amount, etc.)
        normalized_items = reconcile_financials(normalized_items, extracted_data, grand_total)
        
        # 8. Price Watchdog (History Check)
        # Check if these prices are higher than previous purchases
        try:
            from src.persistence import check_inflation_on_analysis
            logger.info("Analyzer: Running Price Watchdog...")
            if driver:
                normalized_items = check_inflation_on_analysis(driver, normalized_items)
            else:
                 logger.warning("Analyzer: No DB Driver available for Price Watchdog.")
        except Exception as e:
            logger.error(f"Price Watchdog Failed: {e}")
            # Non-critical, continue

        # 4. Financial Integrity Check
        validation_flags = []
        
        # Calculate sum of line items from extracted/normalized data
        calculated_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
        stated_total = extracted_data.get("Stated_Grand_Total")
        
        if stated_total:
            try:
                    stated_val = float(stated_total)
                    print(f"DEBUG: Stated Total: {stated_val}, Calculated: {calculated_total}")
                    
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
            "invoice_data": extracted_data, # Return raw extraction as dict
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
    finally:
        # Cleanup temp file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/confirm-invoice", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest):
    """
    Step 2: Receives the verified (and potentially edited) data and persists it to Neo4j.
    """
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        # 1. Re-hydrate Invoice Object from the (possibly edited) invoice_data
        # Note: If frontend edits invoice header, 'request.invoice_data' should reflect that.
        invoice_obj = InvoiceExtraction(**request.invoice_data)
        
        # --- CORRECTION LEARNING (The Brain) ---
        # Detect if user changed Quantity significantly, implying Pack Size error.
        try:
            from src.services.mistake_memory import MEMORY
            
            # Create a map of Raw Items by Product Name to compare
            raw_map = {item.Standard_Item_Name: item for item in invoice_obj.Line_Items}
            
            for confirmed_item in request.normalized_items:
                name = confirmed_item.get("Standard_Item_Name")
                confirmed_qty = confirmed_item.get("Standard_Quantity", 0.0)
                
                if name in raw_map:
                    raw_item = raw_map[name]
                    # AI's guess (Raw_Quantity is what AI saw/extracted)
                    # Note: We need to check what field 'raw_item' actually has for Qty.
                    # Based on schema, InvoiceExtraction -> InvoiceItem -> 'Quantity' (str) or 'Standard_Quantity'
                    ai_qty_val = raw_item.Standard_Quantity or 0.0
                    
                    # Logic: If AI said X, but Human changed to Y, and difference is significant
                    if ai_qty_val > 0 and confirmed_qty > 0 and ai_qty_val != confirmed_qty:
                        # Pack Size Error Pattern: 
                        # e.g. AI saw "10" (Strip) but it was "10x10" so real qty is 100? 
                        # OR AI saw "2" (Boxes) but real qty is "20" (Strips).
                        
                        rule = f"CRITICAL: For item '{name}', if Qty is {ai_qty_val}, it really means {confirmed_qty}. Check Pack Size."
                        MEMORY.add_rule(rule)
                        logger.info(f"Brain: Learned mistake for '{name}' (AI: {ai_qty_val} -> Human: {confirmed_qty})")

        except Exception as e:
            logger.error(f"Brain Learning Failed: {e}")
            
        # 2. Ingest into Neo4j
        # We pass the confirmed normalized_items directly
        ingest_invoice(driver, invoice_obj, request.normalized_items)
        
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
async def get_report(request: Request, invoice_no: str):
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


@app.post("/export-excel")
async def export_excel_endpoint(request: ConfirmInvoiceRequest):
    """
    Step 3 (Optional): Generates an Excel report for the current data.
    """
    try:
        # Convert Pydantic models to dict if needed (here request.invoice_data is already dict)
        excel_bytes = generate_excel(request.invoice_data, request.normalized_items)
        
        # Determine filename
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


# --- History & Inventory Endpoints ---

@app.get("/history", response_model=List[Dict[str, Any]])
async def get_history_endpoint():
    """
    Returns grouped invoice history by Supplier.
    """
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        from src.persistence import get_supplier_history
        return get_supplier_history(driver)
    except Exception as e:
        logger.error(f"History Fetch Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/inventory", response_model=List[Dict[str, Any]])
async def get_inventory_endpoint():
    """
    Returns aggregated inventory (Product Name + MRP).
    """
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        from src.persistence import get_inventory_aggregation
        return get_inventory_aggregation(driver)
    except Exception as e:
        logger.error(f"Inventory Fetch Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class EnrichmentRequest(BaseModel):
    supplier_name: str

@app.post("/enrich-supplier")
async def enrich_supplier_endpoint(request: EnrichmentRequest):
    """
    Triggers an Agent to find missing GST/Phone for a Supplier.
    (Placeholder for Agent Logic - currently just acknowledges)
    """
    # TODO: Implement LangGraph Agent here to search Vector Store or Web
    return {"status": "queued", "message": f"Enrichment started for {request.supplier_name}"}

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
