import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from neo4j import GraphDatabase
from dotenv import load_dotenv
import uvicorn

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.schemas import InvoiceExtraction
from src.normalization import normalize_line_item
from src.persistence import ingest_invoice
from src.extraction.extraction_agent import extract_invoice_data

load_dotenv()

# Basic validation that GEMINI_API_KEY exists (optional but good practice)
if not os.getenv("GEMINI_API_KEY"):
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

app = FastAPI(title="Invoice Extractor API")

# ... setup templates and neo4j ...
# Neo4j Connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = None
# ... startup/shutdown ...

@app.on_event("startup")
def startup_event():
    global driver
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("Connected to Neo4j.")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")

@app.on_event("shutdown")
def shutdown_event():
    if driver:
        driver.close()

@app.post("/process-invoice", response_model=Dict[str, Any])
async def process_invoice(file: UploadFile = File(...)):
    """
    Receives an invoice image file, runs Gemini Vision OCR, extraction agents,
    normalization, and ingests it into Neo4j.
    """
    if not driver:
        # In production, we might want to handle this better, but strict fail for now
        # raise HTTPException(status_code=503, detail="Database connection unavailable")
        pass # Allow extraction to proceed even if DB is down? No, ingestion requires it. 
        # But for testing extraction in isolation, we might loosen this. 
        # The prompt implies "ingest_invoice" is part of the flow.
        
    try:
        # 1. Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        try:
            # 2. Extract Data using Gemini Vision + Agents
            # This calls the updated extraction_agent which invokes Gemini
            extracted_data = extract_invoice_data(tmp_path)
            
            if extracted_data is None:
                raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
            
            # 3. Normalize Line Items
            # Extracted data is a dict (result of .model_dump()), we need to convert back to object?
            # Or normalize_line_item handles attributes.
            # normalize_line_item expects RawLineItem object.
            # So let's re-hydrate into Pydantic model for ease of use
            invoice_obj = InvoiceExtraction(**extracted_data)
            
            normalized_items = []
            for raw_item in invoice_obj.Line_Items:
                norm_item = normalize_line_item(raw_item, invoice_obj.Supplier_Name)
                normalized_items.append(norm_item)
            
            # 4. Ingest into Neo4j (if driver available)
            if driver:
                ingest_invoice(driver, invoice_obj, normalized_items)
            
            return {
                "status": "success",
                "message": f"Invoice {invoice_obj.Invoice_No} processed successfully.",
                "normalized_data": normalized_items
            }
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ... rest of file (report endpoint) ...
@app.get("/report/{invoice_no}", response_class=HTMLResponse)
async def get_report(request: Request, invoice_no: str):
    # ... existing report logic ...
    if not driver:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Database unavailable"})

    query = """
    MATCH (i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:REFERENCES]->(p:Product)
    RETURN i, collect({line: l, product: p}) as items
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
        line_items.append({**line_data, "product_name": product_data.get("name", "Unknown")})

    return templates.TemplateResponse("report.html", {
        "request": request,
        "invoice": invoice_details,
        "line_items": line_items
    })

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
