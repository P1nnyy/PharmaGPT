import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

key = os.getenv("GOOGLE_API_KEY")

print(f"Key loaded: {'Yes' if key else 'No'}")
if key:
    print(f"Key length: {len(key)}")
    print(f"Key starts with: {key[:4]}...")
    print(f"Key ends with: ...{key[-4:]}")
    
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=key)
        print("Attempting to invoke model...")
        response = llm.invoke("Hello")
        print("Success! Response:", response.content)
    except Exception as e:
        print("Error invoking model:")
        print(e)
else:
    print("Please check your .env file.")
