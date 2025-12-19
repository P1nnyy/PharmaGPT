import pandas as pd
import io
from typing import Dict, List, Any

def generate_excel(invoice_data: Dict[str, Any], line_items: List[Dict[str, Any]]) -> bytes:
    """
    Generates an Excel file from the invoice data and line items.
    Returns the file content as bytes.
    """
    # 1. flatten line items for DataFrame
    rows = []
    for idx, item in enumerate(line_items, 1):
        rows.append({
            "Sr No": idx,
            "Item Name": item.get("Standard_Item_Name", ""),
            "Batch": item.get("Batch_No", ""),
            "Expiry": item.get("Expiry_Date", ""),
            "Qty": item.get("Standard_Quantity", 0),
            "MRP": item.get("MRP", 0.0),
            "Rate": item.get("Final_Unit_Cost", 0.0), # Using Landing Cost/Net Rate as Rate column for report
            "Net Amount": item.get("Net_Line_Amount", 0.0)
        })

    # 2. Create DataFrame
    df = pd.DataFrame(rows)
    
    # 3. Create Excel Buffer
    output = io.BytesIO()
    
    # 4. Write to Excel
    # Using openpyxl engine
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Line Items')
        
        # Metadata / Header info could be added to another sheet or top of this one
        # For now, sticking to the user's requested columns list logic
        # Optionally, we can add a Summary Sheet
        summary_data = {
            "Invoice No": [invoice_data.get("Invoice_No")],
            "Supplier": [invoice_data.get("Supplier_Name")],
            "Date": [invoice_data.get("Invoice_Date")],
            "Grand Total": [invoice_data.get("Stated_Grand_Total") or invoice_data.get("Invoice_Amount")]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, index=False, sheet_name='Summary')

    output.seek(0)
    return output.getvalue()
