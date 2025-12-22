import os
import uuid
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load Env Vars FIRST (Before imports that read os.getenv)
load_dotenv()

from src.utils.logging_config import setup_logging, get_logger, request_id_ctx
from src.database.connection import init_driver, close_driver
from src.api.routes import invoices, suppliers, inventory

# Load Config & Logging
setup_logging(log_dir="logs", log_file="app.log")
logger = get_logger("api")

app = FastAPI(title="Invoice Extractor API")

# --- Middleware ---
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as e:
        logger.exception("Middleware Error")
        raise e
    finally:
        request_id_ctx.reset(token)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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

# --- CORS ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://pharmagpt.co",
    "https://api.pharmagpt.co",
    "http://localhost:8000",
    "http://192.168.1.4:5173",
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Event Handlers ---
@app.on_event("startup")
def startup_event():
    init_driver()

@app.on_event("shutdown")
def shutdown_event():
    close_driver()

# --- Include Routers ---
app.include_router(invoices.router)
app.include_router(suppliers.router)
app.include_router(inventory.router)

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
