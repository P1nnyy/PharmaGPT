import shutil
import tempfile
import sys
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load env vars BEFORE imports that might use them
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Depends
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
from src.persistence import ingest_invoice, get_activity_log, get_inventory
from src.workflow.graph import run_extraction_pipeline

# Basic validation that API Key exists (optional but good practice)
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    # Fallback to GEMINI_API_KEY for backward compatibility
    API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logger.warning("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables.")

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Invoice Extractor API")

# Mount Static Directory
os.makedirs("static/invoices", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

# --- Auth & Session Configuration ---
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request as StarletteRequest
from jose import jwt, JWTError
from datetime import datetime, timedelta

# User Configuration from Env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_change_me_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 Days

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    logger.warning("Google OAuth credentials missing. Auth routes will fail.")

# Setup Session Middleware (Required for Authlib 'state' management)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Setup OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Request Models ---

class ConfirmInvoiceRequest(BaseModel):
    invoice_data: Dict[str, Any]
    normalized_items: List[Dict[str, Any]]

# --- API Endpoints ---

@app.get("/auth/google/login")
async def login(request: Request):
    # Absolute URL for callback
    # For local: http://localhost:5001/auth/google/callback
    # For prod: Use https if available
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def auth_callback(request: Request):
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
         
    try:
        from src.persistence import upsert_user
        
        token = await oauth.google.authorize_access_token(request)
        user = token.get('userinfo')
        if not user:
            # Try parsing id_token manually if userinfo not in token dict 
            # (depends on authlib version/provider)
            user = await oauth.google.parse_id_token(request, token)
            
        if not user:
             raise HTTPException(status_code=400, detail="Failed to retrieve user info")
             
        # 1. Upsert User in DB
        user_data = {
            "google_id": user.get("sub"),
            "email": user.get("email"),
            "name": user.get("name"),
            "picture": user.get("picture")
        }
        upsert_user(driver, user_data)
        
        # 2. Create Session Token (JWT)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.get("email")},
            expires_delta=access_token_expires
        )
        
        # 3. Redirect to Frontend with Token
        # Dev: http://localhost:5173
        # Prod: https://pharmagpt.co (or derived from referer/config)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        
        # We redirect to root /?token=... to avoid need for React Router
        response = HTMLResponse(f"""
        <script>
            window.location.href = "{frontend_url}/?token={access_token}";
        </script>
        """)
        return response
        
    except Exception as e:
        logger.error(f"Auth Callback Failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})



# --- Dependencies ---
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user_email(token: str = Depends(oauth2_scheme)):
    """
    Decodes JWT and returns email.
    If fails, raises 401. STRICT MODE.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
             raise HTTPException(status_code=401, detail="Invalid credentials")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
        
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
async def analyze_invoice(file: UploadFile = File(...), user_email: str = Depends(get_current_user_email)):
    """
    Step 1: Analyzes the invoice (OCR + Normalization) but DOES NOT persist to DB.
    Returns the raw and normalized data for frontend verification.
    """
    processing_path = None
    try:
        # Scope 1: File Save PERMANENTLY locally (for History View)
        # Note: In production this should be S3. Here we use local filesystem in /static.
        print(f"Received file: {file.filename} from {user_email}")
        
        file_ext = f".{file.filename.split('.')[-1]}" if '.' in file.filename else ".png"
        file_id = uuid.uuid4().hex
        filename = f"{file_id}{file_ext}"
        
        # Save to static directory directly
        save_dir = "static/invoices"
        os.makedirs(save_dir, exist_ok=True)
        processing_path = os.path.join(save_dir, filename)
        
        with open(processing_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"Saved invoice image to: {processing_path}")
        
        # This relative path is what we store in DB and send to frontend
        static_path = f"/static/invoices/{filename}"
        
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # Scope 2: Extraction
    try:
        # 2. Extract Data using Gemini Vision + Agents (LangGraph)
        print("Starting extraction pipeline...")
        # PASS USER CONTEXT
        # Note: processing_path is absolute or relative to pwd, compatible with vision tools
        extracted_data = await run_extraction_pipeline(processing_path, user_email)
        print("Extraction pipeline completed.")
        
        if extracted_data is None:
            raise HTTPException(status_code=400, detail="Invoice extraction failed validation.")
            
        # INJECT IMAGE PATH INTO EXTRACTED DATA
        # This ensures it travels back to frontend and then back to confirm-invoice
        extracted_data["image_path"] = static_path
        
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
            "invoice_data": extracted_data, # Return raw extraction as dict (now includes image_path)
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
    # finally:
        # DO NOT DELETE FILE - We need it for history now!


@app.post("/confirm-invoice", response_model=Dict[str, Any])
async def confirm_invoice(request: ConfirmInvoiceRequest, user_email: str = Depends(get_current_user_email)):
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
        # Extract supplier details if available
        supplier_details = request.invoice_data.get("supplier_details")
        
        # We pass the confirmed normalized_items directly
        ingest_invoice(driver, invoice_obj, request.normalized_items, user_email=user_email, supplier_details=supplier_details)
        
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
async def get_report(request: Request, invoice_no: str, user_email: str = Depends(get_current_user_email)):
    if not driver:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Database unavailable"})

    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:REFERENCES]->(p:Product)
    RETURN i, collect({line: l, product: p, raw_desc: l.raw_description, stated_net: l.stated_net_amount, batch_no: l.batch_no, hsn_code: l.hsn_code}) as items
    """
    
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no, user_email=user_email).single()
    
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

@app.get("/activity-log")
async def read_activity_log(user_email: str = Depends(get_current_user_email)):
    if not driver:
        return [] 
    try:
        data = get_activity_log(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch activity log: {e}")
        return []

@app.get("/inventory")
async def read_inventory(user_email: str = Depends(get_current_user_email)):
    if not driver:
        return []
    try:
        data = get_inventory(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch inventory: {e}")
        return []

@app.get("/history")
async def read_history(user_email: str = Depends(get_current_user_email)):
    if not driver:
        return []
    try:
        from src.persistence import get_grouped_invoice_history
        data = get_grouped_invoice_history(driver, user_email=user_email)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []

@app.get("/invoices/{invoice_number}/items")
async def read_invoice_items(invoice_number: str, user_email: str = Depends(get_current_user_email)):
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    # Import locally to avoid circular imports if any, or just ensure it's imported at top
    from src.persistence import get_invoice_details
    
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

@app.get("/auth/me")
async def get_current_user_profile(user_email: str = Depends(get_current_user_email)):
    """
    Returns the full profile of the currently logged-in user.
    """
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
        
    query = "MATCH (u:User {email: $email}) RETURN u"
    with driver.session() as session:
        result = session.run(query, email=user_email).single()
        
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
        
    return dict(result["u"])

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=5001, reload=True)
