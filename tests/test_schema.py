import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import RawLineItem, InvoiceExtraction

def test_raw_line_item():
    print("Testing RawLineItem...")
    try:
        item = RawLineItem(
            Original_Product_Description="Test Product",
            Raw_Quantity="10 strips",
            Batch_No="B123",
            Raw_Rate_Column_1=100.0,
            Raw_Rate_Column_2="150.0",
            Raw_Discount_Percentage=10,
            Stated_Net_Amount=900.0
        )
        print("RawLineItem valid:", item)
    except Exception as e:
        print("RawLineItem validation failed:", e)

def test_invoice_extraction():
    print("\nTesting InvoiceExtraction...")
    try:
        invoice = InvoiceExtraction(
            Supplier_Name="Test Supplier",
            Invoice_No="INV-001",
            Invoice_Date="2024-01-01",
            Line_Items=[
                RawLineItem(
                    Original_Product_Description="Item 1",
                    Raw_Quantity=5,
                    Batch_No="X99",
                    Stated_Net_Amount="500"
                )
            ]
        )
        print("InvoiceExtraction valid:", invoice)
    except Exception as e:
        print("InvoiceExtraction validation failed:", e)

if __name__ == "__main__":
    test_raw_line_item()
    test_invoice_extraction()
