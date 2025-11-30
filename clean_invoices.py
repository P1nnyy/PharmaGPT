import json
import os

INVOICES_FILE = "invoices.json"

if os.path.exists(INVOICES_FILE):
    with open(INVOICES_FILE, "r") as f:
        invoices = json.load(f)
    
    # Filter out invoices with null ID or .png extension (screenshots)
    cleaned_invoices = [
        inv for inv in invoices 
        if inv.get("id") is not None and not inv.get("filename", "").endswith(".png")
    ]
    
    print(f"Removed {len(invoices) - len(cleaned_invoices)} invalid invoices.")
    
    with open(INVOICES_FILE, "w") as f:
        json.dump(cleaned_invoices, f, indent=2)
else:
    print("invoices.json not found.")
