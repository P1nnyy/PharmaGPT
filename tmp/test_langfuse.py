import os
from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()

from langfuse import observe

@observe()
def test_langfuse_cloud():
    print(f"Testing Langfuse Cloud via @observe...")
    print(f"Host: {os.getenv('LANGFUSE_HOST')}")
    
    # Just a dummy function to trigger a trace
    return "Success"

if __name__ == "__main__":
    test_langfuse_cloud()
    from langfuse import Langfuse
    Langfuse().flush()
    print("Done. Please check your Langfuse Cloud dashboard.")
