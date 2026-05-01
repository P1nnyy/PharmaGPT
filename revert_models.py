import os
import glob

def revert_files():
    base_dir = "/Users/pranavgupta/Desktop/untitled folder/Invoice Extractor/src"
    for filepath in glob.glob(os.path.join(base_dir, "**", "*.py"), recursive=True):
        with open(filepath, "r") as f:
            content = f.read()
            
        if "gemini-2.0-flash-lite" in content:
            content = content.replace("gemini-2.0-flash-lite", "gemini-2.0-flash")
            with open(filepath, "w") as f:
                f.write(content)
            print(f"Reverted {filepath}")

revert_files()
