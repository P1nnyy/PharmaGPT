import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

for model in ["text-embedding-004", "gemini-embedding-2"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={API_KEY}"
    payload = {
        "model": f"models/{model}",
        "content": {"parts": [{"text": "Hello World"}]}
    }
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
    print(f"{model}: {r.status_code}")
