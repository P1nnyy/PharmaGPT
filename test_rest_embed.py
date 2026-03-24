import os
import requests
url = f"https://generativelanguage.googleapis.com/v1/models/text-embedding-004:embedContent?key={os.getenv('GOOGLE_API_KEY')}"
headers = {"Content-Type": "application/json"}
payload = {
    "model": "models/text-embedding-004",
    "content": {"parts": [{"text": "Paracetamol 500"}]}
}
try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    print("SUCCESS V1")
except Exception as e:
    print(f"FAILED V1: {e}")
