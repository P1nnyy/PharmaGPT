import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    with open("dummy.txt", "w") as f:
        f.write("This is a dummy file for cache testing.")
        
    print("Uploading file...")
    file = await client.aio.files.upload(file="dummy.txt")
    print(f"File uploaded: {file.name}")
    
    print("Creating cache...")
    cached_content = await client.aio.caches.create(
        model='gemini-2.0-flash',
        config=types.CreateCachedContentConfig(contents=[file], ttl='900s')
    )
    print(f"Cache created: {cached_content.name}")
    
    print("Generating content from cache...")
    response = await client.aio.models.generate_content(
        model='gemini-2.0-flash',
        contents="What is in the file?",
        config=types.GenerateContentConfig(cached_content=cached_content.name)
    )
    print("Response:", response.text)
    
    # Cleanup
    await client.aio.caches.delete(name=cached_content.name)

asyncio.run(main())
