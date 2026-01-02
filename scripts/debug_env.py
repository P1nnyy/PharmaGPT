import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

print(f"DEBUG_ENV: CLIENT_ID=|{client_id}|")
print(f"DEBUG_ENV: CLIENT_SECRET_LEN={len(client_secret) if client_secret else 0}")
