
import requests
import json
import os

# Define payload matching ConfirmInvoiceRequest
payload = {
    "invoice_data": {
        "Invoice_No": "TEST-530-ERROR",
        "Invoice_Date": "2023-10-27",
        "Grand_Total": 100.0,
        "supplier_details": {"name": "Test Supplier"}
    },
    "normalized_items": []
}

url = "http://localhost:5001/invoices/confirm"

try:
    print(f"Sending POST to {url}...")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request Failed: {e}")
