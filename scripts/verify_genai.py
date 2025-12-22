import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY not found.")
    exit(1)

print(f"Using API Key: {API_KEY[:5]}...")

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Hello! Are you working?")
    print(f"Response: {response.text}")
    print("SUCCESS: Gemini API is working.")
except Exception as e:
    print(f"FAILURE: Gemini API Check Failed: {e}")
