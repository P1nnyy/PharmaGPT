import os
# CRITICAL: Fix for Tunnel/VPN DNS Resolution with GRPC
os.environ["GRPC_DNS_RESOLVER"] = "native"

import uuid
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
# Removed imports to avoid circular deps. Metrics moved to src/api/metrics.py

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
from src.api.routes.config import router as config_router
from src.api.routes.invitations import router as invitations_router

# --- Logging Configuration ---
setup_logging(log_dir="logs", log_file="app.log")
logger = get_logger("api")

app = FastAPI(title="Invoice Extractor API")

# --- Middleware ---
@app.middleware("http")
async def diagnostic_middleware(request: Request, call_next):
    """
    Injected Diagnostic for Tunnel/Proxy issues.
    """
    logger.debug(f"DEBUG: Scheme: {request.url.scheme}, Host: {request.url.hostname}, Headers: {dict(request.headers)}")
    return await call_next(request)

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
    allow_origins=["https://dev.pharmagpt.co", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY, 
    same_site="lax", 
    https_only=False
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
app.include_router(config_router)
app.include_router(invitations_router)

# --- Observability & Custom Metrics ---

# Metrics are imported here to ensure they are registered with the default registry
# before the Instrumentator instruments the app.
from src.api.metrics import (
    invoice_healer_triggered_total,
    invoice_unreconciled_value,
    circuit_breaker_tripped_total,
    invoice_extraction_retries_total
)

# Standard instrumentator (serves as base and exposes /metrics)
Instrumentator().instrument(app).expose(app)

# --- Static Frontend Serving ---
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))

# Mount the entire dist directory as a static fallback (serves assets, logo, etc.)
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


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
    port = int(os.environ.get("PORT", 5005))
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=port, reload=False)
