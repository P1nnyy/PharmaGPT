import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    # Tell SDK to use v1beta explicitly
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hi"
    )
    print(f"Response: {response.text}")

asyncio.run(test())
