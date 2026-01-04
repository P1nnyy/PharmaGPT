
import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def test_gemini():
    print("Testing Gemini Connectivity...")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env")
        return

    genai.configure(api_key=api_key)
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = await model.generate_content_async("Hello, can you hear me?")
        print(f"Success! Response: {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
