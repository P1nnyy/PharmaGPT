from typing import List, Dict, Any

def format_currency(value: float) -> str:
    """Formats a float as a currency string (e.g., ₹ 1,234.56)"""
    return f"₹ {value:,.2f}"

def format_invoice_for_display(normalized_items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Transforms normalized line items into the final user verification table format.
    
    Required Headers:
    - Sr No.
    - Item Name (Standard_Item_Name)
    - Pack Size
    - Qty
    - Cost Price (Per Unit)
    - Discount (₹)
    - Tax Rate (%)
    - Net Amount (Line Total)
    """
    display_rows = []
    
    for idx, item in enumerate(normalized_items):
        row = {
            "Sr No.": str(idx + 1),
            "Item Name": item.get("Standard_Item_Name", ""),
            "Pack Size": item.get("Pack_Size_Description", ""),
            "Qty": str(item.get("Standard_Quantity", "")),
            "Cost Price (Per Unit)": format_currency(item.get("Calculated_Cost_Price_Per_Unit", 0.0)),
            "Discount (₹)": format_currency(item.get("Discount_Amount_Currency", 0.0)),
            "Tax Rate (%)": f"{item.get('Raw_GST_Percentage', 0)}%", 
            "Net Amount (Line Total)": format_currency(item.get("Net_Line_Amount", 0.0))
        }
        display_rows.append(row)
        
    return display_rows
