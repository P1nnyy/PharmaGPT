import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
response = client.models.embed_content(
    model="text-embedding-004",
    contents="Hello World"
)
print(len(response.embeddings[0].values))
