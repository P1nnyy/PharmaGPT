import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env vars BEFORE imports that might use them
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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
    "http://localhost:5173",  # Vite Default
    "http://localhost:3000",
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

@app.get("/logs")
async def get_logs(lines: int = 100):
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
        # 3.b Apply Global Proration (Phase 3)
        global_discount = parse_float(extracted_data.get("Global_Discount_Amount", 0.0))
        freight = parse_float(extracted_data.get("Freight_Charges", 0.0))
        
        # Sum Split Taxes
        sgst = parse_float(extracted_data.get("SGST_Amount", 0.0))
        cgst = parse_float(extracted_data.get("CGST_Amount", 0.0))
        igst = parse_float(extracted_data.get("IGST_Amount", 0.0))
        global_tax = sgst + cgst + igst
        
        if global_discount > 0 or freight > 0 or global_tax > 0:
            from src.normalization import distribute_global_modifiers
            normalized_items = distribute_global_modifiers(normalized_items, global_discount, freight, global_tax)
        
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

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
