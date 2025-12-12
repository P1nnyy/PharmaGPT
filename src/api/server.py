import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pydantic import BaseModel
import uvicorn

from src.schemas import InvoiceExtraction
from src.normalization import normalize_line_item
from src.persistence import ingest_invoice
from src.extraction.extraction_agent import extract_invoice_data

load_dotenv()

# Basic validation that API Key exists (optional but good practice)
if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    print("WARNING: GEMINI_API_KEY or GOOGLE_API_KEY not found in environment variables.")

app = FastAPI(title="Invoice Extractor API")

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

@app.post("/analyze-invoice", response_model=Dict[str, Any])
async def analyze_invoice(file: UploadFile = File(...)):
    """
    Step 1: Analyzes the invoice (OCR + Normalization) but DOES NOT persist to DB.
    Returns the raw and normalized data for frontend verification.
    """
    tmp_path = None
    try:
        # 1. Save uploaded file to temp
        print(f"Received file: {file.filename}")
        suffix = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".tmp"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        print(f"Saved temp file to: {tmp_path}")
        
        try:
            # 2. Extract Data using Gemini Vision + Agents
            # Note: File is closed here, preventing Windows Permission Denied errors
            print("Starting extraction...")
            extracted_data = extract_invoice_data(tmp_path)
            print("Extraction completed.")
            
            if extracted_data is None:
                raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
            
            # 3. Normalize Line Items
            # Hydrate into Pydantic model
            invoice_obj = InvoiceExtraction(**extracted_data)
            
            normalized_items = []
            for raw_item in invoice_obj.Line_Items:
                norm_item = normalize_line_item(raw_item, invoice_obj.Supplier_Name)
                normalized_items.append(norm_item)
            
            # 4. Financial Integrity Check
            validation_flags = []
            
            # Calculate sum of line items from extracted/normalized data
            calculated_total = sum(item.Net_Line_Amount for item in normalized_items)
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

        finally:
            # Cleanup temp file
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except Exception as e:
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
        print(f"Database ingestion failed: {e}")
        import traceback
        traceback.print_exc()
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
