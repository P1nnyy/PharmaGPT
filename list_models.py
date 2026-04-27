import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}")
for m in r.json().get("models", []):
    if "embedding" in m["name"]:
        print(m["name"])
