import asyncio
import os

# Unset GCP variables completely
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
if "GCP_PROJECT" in os.environ:
    del os.environ["GCP_PROJECT"]

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    with open("dummy.txt", "rb") as f:
        data = f.read()

    part = types.Part.from_bytes(data=data, mime_type='text/plain')
    
    print("Testing inline generation...", flush=True)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[part, "What is the content?"]
    )
    print(f"Response: {response.text}")

asyncio.run(test())
