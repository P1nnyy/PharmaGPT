
import os
from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST")

print(f"Testing Langfuse Connection...")
print(f"Host: {host}")
print(f"Public Key: {public_key[:8]}...")

try:
    langfuse = Langfuse()
    if langfuse.auth_check():
        print("✅ Connection Successful! Credentials are valid.")
    else:
        print("❌ Connection Failed. Invalid credentials.")
        exit(1)
except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit(1)
