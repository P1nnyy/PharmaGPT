from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from vision_agent import analyze_bill_image
from agent import run_agent
from shop_manager import PharmaShop
import uvicorn
import os
import json
import uuid
import shutil
from datetime import datetime

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory to serve images
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

shop = PharmaShop()

# Simple JSON-based persistence for invoices
INVOICES_FILE = "invoices.json"

def load_invoices():
    if os.path.exists(INVOICES_FILE):
        with open(INVOICES_FILE, "r") as f:
            return json.load(f)
    return []

def save_invoices(invoices):
    with open(INVOICES_FILE, "w") as f:
        json.dump(invoices, f, indent=2)

@app.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...)):
    try:
        # Generate unique filename
        file_ext = file.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        filepath = os.path.join("uploads", filename)
        
        # Save file to disk
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Analyze image
        with open(filepath, "rb") as f:
            contents = f.read()
            extracted_data = analyze_bill_image(contents)
            
        # Handle both old (list) and new (dict) formats for backward compatibility
        if isinstance(extracted_data, list):
            items = extracted_data
            summary = {
                "invoice_number": str(uuid.uuid4())[:8],
                "invoice_date": datetime.now().strftime("%Y-%m-%d"),
                "net_amount": sum(item.get("rate", item.get("mrp", 0)) * item.get("quantity_packs", 0) for item in extracted_data)
            }
        else:
            items = extracted_data.get("items", [])
            summary = extracted_data.get("summary", {})
            
        # Create invoice record
        invoice_record = {
            "id": summary.get("invoice_number", str(uuid.uuid4())),
            "filename": filename,
            "image_url": f"http://localhost:8000/uploads/{filename}",
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "invoice_date": summary.get("invoice_date"),
            "net_amount": summary.get("net_amount"),
            "items": items
        }
        
        # Save to history
        invoices = load_invoices()
        invoices.insert(0, invoice_record) # Add to top
        save_invoices(invoices)
        
        return {
            "status": "success", 
            "data": items, 
            "summary": summary,
            "invoice_id": invoice_record["id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/invoices")
def get_invoices():
    try:
        return {"invoices": load_invoices()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent")
async def chat_agent(query: str):
    try:
        response = run_agent(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import List, Optional

class InventoryItem(BaseModel):
    product_name: str
    batch_number: str
    expiry_date: str
    quantity_packs: int
    pack_size: int = 10
    mrp: float = 10.0
    rate: float = 5.0
    manufacturer: str = "Generic Pharma Co."
    dosage_form: str = "Tablet"

@app.post("/api/inventory/add")
async def add_inventory(items: List[InventoryItem]):
    print(f"📥 Received inventory commit request with {len(items)} items")
    try:
        results = []
        for item in items:
            print(f"Processing item: {item}")
            result = shop.add_medicine_stock(
                product_name=item.product_name,
                batch_id=item.batch_number,
                expiry_date=item.expiry_date,
                qty_packs=item.quantity_packs,
                pack_size=item.pack_size,
                mrp=item.mrp,
                buy_price=item.rate,
                manufacturer_name=item.manufacturer,
                dosage_form=item.dosage_form
            )
            print(f"✅ Result: {result}")
            results.append(result)
        return {"status": "success", "results": results}
    except Exception as e:
        print(f"❌ Error adding inventory: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory")
def get_inventory():
    try:
        data = shop.check_inventory()
        return {"inventory": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
