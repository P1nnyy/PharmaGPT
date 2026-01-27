import os
import uuid
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.core.config import SECRET_KEY, get_base_url
from src.services.database import connect_db, close_db
from src.services.storage import init_storage_client
from src.utils.logging_config import setup_logging, get_logger, request_id_ctx

# Import Routers
from src.api.routes.auth import router as auth_router
from src.api.routes.products import router as products_router
from src.api.routes.invoices import router as invoices_router
from src.api.routes.reporting import router as reporting_router
from src.api.routes.inventory import router as inventory_router
from src.api.routes.system import router as system_router

# --- Logging Configuration ---
setup_logging(log_dir="logs", log_file="app.log")
logger = get_logger("api")

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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY, 
    https_only=False,  
    same_site='lax',   
    max_age=86400      
)

# Proxy Headers (Must be last added to be outermost)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# --- Include Routers ---
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(invoices_router)
app.include_router(reporting_router)
app.include_router(inventory_router)
app.include_router(system_router)

# --- Observability ---
Instrumentator().instrument(app).expose(app)

# --- Startup / Shutdown ---
@app.on_event("startup")
def startup_event():
    connect_db() 
    init_storage_client()
    # Ensure static directory exists if needed
    # os.makedirs("static", exist_ok=True)
    # app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("shutdown")
def shutdown_event():
    close_db()

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=5001, reload=True)
