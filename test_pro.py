import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    print("Testing gemini-2.0-pro-exp-02-05...")
    try:
        response = client.models.generate_content(
            model="gemini-2.0-pro-exp-02-05",
            contents="Hi"
        )
        print(f"Success: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
