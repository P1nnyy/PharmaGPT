
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from typing import Dict, Any

from src.core.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_base_url, get_frontend_url
)
from src.services.database import get_db_driver
from src.domain.persistence import upsert_user
from src.utils.logging_config import get_logger

logger = get_logger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# --- OAuth Setup ---
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    logger.warning("Google OAuth credentials missing. Auth routes will fail.")

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Helper Functions ---

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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

# --- Endpoints ---

@router.get("/google/login")
async def login(request: Request):
    # Absolute URL for callback
    logger.info(f"Login Request Headers: {dict(request.headers)}") # DEBUG HEADERS
    base_url = get_base_url()
    redirect_uri = f"{base_url}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def auth_callback(request: Request):
    driver = get_db_driver()
    if not driver:
         raise HTTPException(status_code=503, detail="Database unavailable")
         
    try:
        # With ProxyHeadersMiddleware, Authlib should auto-detect the correct redirect_uri
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
        frontend_base = get_frontend_url()
        
        # We redirect to root /?token=... to avoid need for React Router
        response = HTMLResponse(f"""
        <script>
            window.location.href = "{frontend_base}/?token={access_token}";
        </script>
        """)
        return response
        
    except Exception as e:
        logger.error(f"Auth Callback Failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/me")
async def get_current_user_profile(user_email: str = Depends(get_current_user_email)):
    """
    Returns the full profile of the currently logged-in user.
    """
    driver = get_db_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database unavailable")
        
    query = "MATCH (u:User {email: $email}) RETURN u"
    with driver.session() as session:
        result = session.run(query, email=user_email).single()
        
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
        
    return dict(result["u"])
