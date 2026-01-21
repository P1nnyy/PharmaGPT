
try:
    from langfuse import observe
    print("SUCCESS: from langfuse import observe works")
except ImportError as e:
    print(f"ERROR: {e}")
