
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# --- Configuration Constants ---

# Google Auth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_change_me_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 Days

# R2 / S3
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_DOMAIN = os.getenv("R2_PUBLIC_DOMAIN")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Gemini API
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# --- Helper Functions ---

def get_base_url() -> str:
    """
    Returns the explicitly configured BASE_URL for the backend.
    Defaults to http://localhost:5001 if not set.
    """
    # Priority:
    # 1. BASE_URL (Explicit Backend URL from .env)
    # 2. VITE_API_BASE_URL (Legacy/Frontend var)
    # 3. Default
    return os.getenv("BASE_URL") or os.getenv("VITE_API_BASE_URL") or "http://localhost:5001"

def get_frontend_url() -> str:
    """
    Returns the frontend URL for redirects.
    """
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip('/')
