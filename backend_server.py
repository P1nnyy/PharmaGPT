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
from pydantic import BaseModel
from typing import List

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

from fastapi.responses import JSONResponse

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
            
        # Handle new nested format with metadata
        if isinstance(extracted_data, dict) and "metadata" in extracted_data:
            items = extracted_data.get("items", [])
            metadata = extracted_data.get("metadata", {})
            
            # Extract metadata fields
            supplier_name = metadata.get("supplier_name", "Unknown Supplier")
            invoice_number = metadata.get("invoice_number", str(uuid.uuid4())[:8])
            invoice_date = metadata.get("invoice_date", datetime.now().strftime("%Y-%m-%d"))
            
            summary = {
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "supplier_name": supplier_name,
                "net_amount": sum(item.get("buy_price", item.get("rate", item.get("mrp", 0))) * (item.get("quantity") or item.get("quantity_packs") or 0) for item in items)
            }
        # Handle old list format
        elif isinstance(extracted_data, list):
            items = extracted_data
            summary = {
                "invoice_number": str(uuid.uuid4())[:8],
                "invoice_date": datetime.now().strftime("%Y-%m-%d"),
                "supplier_name": "Unknown Supplier",
                "net_amount": sum(item.get("buy_price", item.get("rate", item.get("mrp", 0))) * (item.get("quantity") or item.get("quantity_packs") or 0) for item in extracted_data)
            }
        # Handle old dict format without metadata
        else:
            items = extracted_data.get("items", [])
            summary = extracted_data.get("summary", {})
            summary["supplier_name"] = summary.get("supplier_name", "Unknown Supplier")

        # --- DUPLICATE CHECK ---
        existing_id = shop.check_invoice_exists(summary["invoice_number"], summary["supplier_name"])
        if existing_id:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Duplicate",
                    "message": "Bill exists. Merge?",
                    "can_merge": True,
                    "existing_id": existing_id,
                    "data": items, # Return data so frontend can show/merge it
                    "summary": summary
                }
            )
            
        # Create invoice record
        invoice_record = {
            "id": summary.get("invoice_number", str(uuid.uuid4())),
            "filename": filename,
            "image_url": f"http://localhost:8000/uploads/{filename}",
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "invoice_date": summary.get("invoice_date"),
            "supplier": summary.get("supplier_name"),
            "net_amount": summary.get("net_amount"),
            "items": items
        }
        
        # Save to history (JSON)
        invoices = load_invoices()
        invoices.insert(0, invoice_record) # Add to top
        save_invoices(invoices)
        
        # Save to Neo4j (Graph)
        try:
            shop.create_invoice_record(invoice_record)
        except Exception as e:
            print(f"⚠️ Failed to save invoice to Neo4j: {e}")
        
        return {
            "status": "success", 
            "data": items, 
            "summary": summary,
            "invoice_id": invoice_record["id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MergeRequest(BaseModel):
    items: List[dict]
    summary: dict

@app.post("/api/invoices/merge")
async def merge_invoice(request: MergeRequest):
    try:
        # Construct invoice_data from request
        invoice_data = {
            "items": request.items,
            "supplier": request.summary.get("supplier_name"),
            "id": request.summary.get("invoice_number")
        }
        
        results = shop.merge_invoice_stock(invoice_data)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/invoices")
def get_invoices():
    try:
        return {"invoices": load_invoices()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteInvoicesRequest(BaseModel):
    invoice_ids: List[str]

@app.post("/api/invoices/delete")
async def delete_invoices(request: DeleteInvoicesRequest):
    try:
        invoices = load_invoices()
        initial_count = len(invoices)
        # Filter out invoices whose IDs are in the request
        updated_invoices = [inv for inv in invoices if inv["id"] not in request.invoice_ids]
        
        if len(updated_invoices) < initial_count:
            save_invoices(updated_invoices)
            
        return {"status": "success", "deleted_count": initial_count - len(updated_invoices)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent")
async def chat_agent(query: str):
    try:
        response = run_agent(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re

class InventoryItem(BaseModel):
    product_name: Optional[str] = "Unknown Product"
    batch_number: Optional[str] = "UNKNOWN"
    expiry_date: Optional[str] = None
    quantity: Optional[int] = 0
    pack_label: Optional[str] = Field("1x1", description="Exact text from bill like '1x15', '200ml'")
    pack_size: Optional[int] = Field(None, description="Atomic count")
    mrp: Optional[float] = 0.0
    rate: Optional[float] = 0.0
    buy_price: Optional[float] = 0.0
    manufacturer: Optional[str] = "Generic Pharma Co."
    dosage_form: Optional[str] = "Tablet"
    hsn_code: Optional[str] = None
    mfg_date: Optional[str] = None
    is_free: Optional[bool] = False
    gst_rate: Optional[float] = 0.0

    @validator('dosage_form', pre=True, always=True)
    def normalize_unit_type(cls, v):
        if not v:
            return "Tablet"
        
        s = str(v).lower().strip()
        
        if s in ["tab", "tabs", "tablet", "tablets", "t"]:
            return "Tablet"
        if s in ["cap", "caps", "capsule", "capsules"]:
            return "Capsule"
        if s in ["inj", "vial", "amp", "injection"]:
            return "Injection"
        if s in ["syp", "syrup", "susp", "liq", "liquid"]:
            return "Syrup"
        if s in ["crm", "cream", "oint", "ointment", "gel"]:
            return "Cream"
            
        return v.title()

    @validator('quantity', pre=True, always=True)
    def set_quantity(cls, v):
        if v is None: return 0
        try:
            return int(v)
        except:
            return 0

    @validator('pack_size', always=True, pre=True)
    def derive_pack_size(cls, v, values):
        if v is not None:
            try:
                if int(v) > 0: return int(v)
            except:
                pass
        
        label = values.get('pack_label')
        if not label:
            return 1
            
        # Try to parse "1x15" or "10x10"
        match = re.search(r'(\d+)\s*[xX]\s*(\d+)', str(label))
        if match:
            return int(match.group(2))
            
        # Try to parse "15T" or "10s"
        match = re.search(r'(\d+)\s*[tTsS]', str(label))
        if match:
            return int(match.group(1))
            
        return 1

@app.post("/api/inventory/add")
async def add_inventory(items: List[InventoryItem]):
    print(f"📥 Received inventory commit request with {len(items)} items")
    try:
        results = []
        for item in items:
            print(f"Processing item: {item}")
            
            # Determine buy price (prefer buy_price, fallback to rate, fallback to 0)
            final_buy_price = item.buy_price if item.buy_price is not None else (item.rate if item.rate is not None else 0.0)
            
            result = shop.add_medicine_stock(
                product_name=item.product_name,
                batch_id=item.batch_number,
                expiry_date=item.expiry_date,
                qty_packs=item.quantity,
                pack_size=item.pack_size,
                mrp=item.mrp,
                buy_price=final_buy_price,
                manufacturer_name=item.manufacturer,
                dosage_form=item.dosage_form,
                tax_rate=item.gst_rate / 100.0 if item.gst_rate else 0.0,
                hsn_code=item.hsn_code,
                mfg_date=item.mfg_date,
                pack_label=item.pack_label
            )
            print(f"✅ Result: {result}")
            results.append(result)
        return {"status": "success", "results": results}
    except Exception as e:
        print(f"❌ Error adding inventory: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteRequest(BaseModel):
    batch_numbers: List[str]

@app.post("/api/inventory/delete")
async def delete_inventory_items(request: DeleteRequest):
    try:
        results = []
        for batch_id in request.batch_numbers:
            success = shop.delete_batch(batch_id)
            results.append({"batch": batch_id, "success": success})
        return {"status": "success", "results": results}
    except Exception as e:
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
