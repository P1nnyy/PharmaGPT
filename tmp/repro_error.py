import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.domain.schemas import InvoiceExtraction, RawLineItem

def reproduce_error():
    print("Attempting to initialize InvoiceExtraction with taxable_value=None...")
    try:
        data = {
            "Supplier_Name": "Test Supplier",
            "Invoice_No": "123",
            "Line_Items": [],
            "taxable_value": None  # This should cause the error
        }
        invoice = InvoiceExtraction(**data)
        print("Success! (Unexpected)")
    except Exception as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    reproduce_error()
