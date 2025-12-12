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



from src.schemas import InvoiceExtraction
from src.normalization import normalize_line_item
from src.persistence import ingest_invoice
from src.extraction.extraction_agent import extract_invoice_data

load_dotenv()

# Basic validation that API Key exists (optional but good practice)
if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    print("WARNING: GEMINI_API_KEY or GOOGLE_API_KEY not found in environment variables.")

app = FastAPI(title="Invoice Extractor API")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

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
        print(f"Failed to connect to Neo4j: {e} - Application will start in partial mode (No DB)")

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
                try:
                    ingest_invoice(driver, invoice_obj, normalized_items)
                    return {
                        "status": "success",
                        "message": f"Invoice {invoice_obj.Invoice_No} processed successfully.",
                        "normalized_data": normalized_items
                    }
                except Exception as db_err:
                    print(f"Database ingestion failed: {db_err}")
                    return {
                        "status": "partial_success", 
                        "message": "Extraction successful, but database ingestion failed.",
                        "normalized_data": normalized_items,
                        "error": str(db_err)
                    }
            else:
                 return {
                    "status": "partial_success", 
                    "message": "Extraction successful, but database unavailable.",
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
