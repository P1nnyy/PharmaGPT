import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    print("Uploading file...")
    file = client.files.upload(file="dummy.txt")
    print(f"File uploaded. Name: {file.name}")
    
    # Try using it in generation
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[file, "What is in this file?"]
    )
    print(f"Response: {response.text}")

asyncio.run(test())
