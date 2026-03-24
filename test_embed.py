import os
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1'})
try:
    res = client.models.embed_content(model="text-embedding-004", contents="test", config={"output_dimensionality": 768})
    print("SUCCESS text-embedding-004")
except Exception as e:
    print(f"FAILED text-embedding-004: {e}")

try:
    res = client.models.embed_content(model="models/text-embedding-004", contents="test", config={"output_dimensionality": 768})
    print("SUCCESS models/text-embedding-004")
except Exception as e:
    print(f"FAILED models/text-embedding-004: {e}")

