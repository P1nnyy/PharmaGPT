
import requests
import json
import os
from dotenv import load_dotenv
from jose import jwt
from datetime import datetime, timedelta

load_dotenv()

url = "http://localhost:5001/analyze-invoice"
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkeyforlocaldevstoredinenv")
ALGORITHM = "HS256"

# Generate Token
expire = datetime.utcnow() + timedelta(minutes=15)
to_encode = {"sub": "testuser@example.com", "exp": expire}
token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

headers = {
    "Authorization": f"Bearer {token}"
}

# Dummy files
files = [
    ("files", ("test1.txt", "dummy content 1", "text/plain")),
    ("files", ("test2.txt", "dummy content 2", "text/plain"))
]

print(f"Sending authenticated batch request to {url} with 2 files...")

try:
    response = requests.post(url, files=files, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}...") 
except Exception as e:
    print(f"Error: {e}")
