import sys
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
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

load_dotenv()

app = FastAPI(title="Invoice Extractor API")

# Setup Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

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
        print(f"Failed to connect to Neo4j: {e}")

@app.on_event("shutdown")
def shutdown_event():
    if driver:
        driver.close()

@app.post("/process-invoice", response_model=Dict[str, Any])
async def process_invoice(invoice: InvoiceExtraction):
    """
    Receives raw invoice extraction data, normalizes it, and ingests it into Neo4j.
    """
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    try:
        # 1. Normalize Line Items
        normalized_items = []
        for raw_item in invoice.Line_Items:
            norm_item = normalize_line_item(raw_item, invoice.Supplier_Name)
            normalized_items.append(norm_item)
        
        # 2. Ingest into Neo4j
        ingest_invoice(driver, invoice, normalized_items)
        
        return {
            "status": "success",
            "message": f"Invoice {invoice.Invoice_No} processed successfully.",
            "normalized_data": normalized_items
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/{invoice_no}", response_class=HTMLResponse)
async def get_report(request: Request, invoice_no: str):
    """
    Displays the 'Clean Invoice' table for a given invoice number.
    """
    if not driver:
        # For demo purposes, render standard error if DB down
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
