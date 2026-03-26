from langfuse import Langfuse
import os
from dotenv import load_dotenv
import time

load_dotenv()

def test_langfuse():
    public = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")
    
    print(f"Testing Langfuse v3 with Public: {public[:10]}... | Host: {host}")
    
    lf = Langfuse(public_key=public, secret_key=secret, host=host)
    
    # In v3, you can use start_observation for traces/spans
    # Or just use the observe decorator which is standard
    try:
        # Create a manual trace/span
        with lf.observe(name="manual-v3-test") as span:
            span.update(input="Testing v3 connection")
            time.sleep(1)
            span.update(output="Success from Antigravity v3")
            
        print("Flushing...")
        lf.flush()
        print("Done. Check Langfuse UI.")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_langfuse()
