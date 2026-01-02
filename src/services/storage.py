
import boto3
import os
from src.core.config import R2_ENDPOINT_URL, AWS_ACCESS_KEY, AWS_SECRET_KEY, R2_BUCKET_NAME, R2_PUBLIC_DOMAIN
from src.utils.logging_config import get_logger

logger = get_logger("storage")

s3_client = None

def init_storage_client():
    """
    Initializes the S3/R2 client.
    """
    global s3_client
    if R2_ENDPOINT_URL and AWS_ACCESS_KEY and AWS_SECRET_KEY:
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT_URL,
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY
            )
            logger.info("R2/S3 Client Initialized Successfully")
        except Exception as e:
            logger.error(f"Failed to initialize R2/S3 Client: {e}")
    else:
        logger.warning("R2/S3 credentials not found. Storage will be disabled.")

def get_storage_client():
    return s3_client

def upload_to_r2(file_obj, filename: str) -> str:
    """
    Uploads a file-like object to R2/S3 and returns the public URL.
    """
    if not s3_client:
        # Lazy init or check (optional, but good strictly)
        init_storage_client()
        
    if not s3_client or not R2_BUCKET_NAME:
        logger.warning("R2 not configured. Falling back to local storage logic (URL might be broken if not handled).")
        return None

    try:
        s3_client.upload_fileobj(
            file_obj,
            R2_BUCKET_NAME,
            filename,
            ExtraArgs={'ContentType': 'image/jpeg'} # Generic or detect
        )
        
        # Construct URL
        # If public domain is set, use it. Else fall back to some r2.dev url (not reliable)
        if R2_PUBLIC_DOMAIN:
            return f"{R2_PUBLIC_DOMAIN}/{filename}"
        
        return f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{filename}"
        
    except Exception as e:
        logger.error(f"R2 Upload Failed: {e}")
        return None
