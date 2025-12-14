from typing import List, Dict, Any
from src.schemas import InvoiceExtraction, NormalizedLineItem
from src.normalization import parse_float

def ingest_invoice(driver, invoice_data: InvoiceExtraction, normalized_items: List[Dict[str, Any]]):
    """
    Ingests invoice and line item data into Neo4j.
    
    Creates/Merges:
    - (:Invoice)
    - (:Product)
    - (:Line_Item)
    
    Relationships:
    - (:Invoice)-[:CONTAINS]->(:Line_Item)
    - (:Line_Item)-[:REFERENCES]->(:Product)
    """
    
    # Calculate Grand Total from line items to ensure consistency
    grand_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
    
    with driver.session() as session:
        # 1. Merge Invoice
        # Using a transaction for atomicity
        session.execute_write(_create_invoice_tx, invoice_data, grand_total)
        
    # 2. Process Line Items
        for raw_item, item in zip(invoice_data.Line_Items, normalized_items):
            session.execute_write(_create_line_item_tx, invoice_data.Invoice_No, item, raw_item)

def _create_invoice_tx(tx, invoice_data: InvoiceExtraction, grand_total: float):
    query = """
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier_name})
    ON CREATE SET 
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.created_at = timestamp()
    ON MATCH SET
        i.grand_total = $grand_total,
        i.updated_at = timestamp()
    """
    tx.run(query, 
           invoice_no=invoice_data.Invoice_No, 
           supplier_name=invoice_data.Supplier_Name,
           invoice_date=invoice_data.Invoice_Date,
           grand_total=grand_total)

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any):
    query = """
    MATCH (i:Invoice {invoice_number: $invoice_no})
    
    // 1. Merge Product (Standard Name)
    MERGE (p:Product {name: $standard_item_name})
    
    // 2. Merge HSN Node (NEW: Optimized for Analytics)
    MERGE (h:HSN {code: $hsn_code})
    
    // 3. Create Line Item
    CREATE (l:Line_Item {
        pack_size: $pack_size,
        quantity: $quantity,
        cost_price: $cost_price,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,   // Keep property for easy access
        mrp: $mrp
    })
    
    // 4. Connect Graph
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:REFERENCES]->(p)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
    """
    
    tx.run(query,
           invoice_no=invoice_no,
           standard_item_name=item.get("Standard_Item_Name"),
           pack_size=item.get("Pack_Size_Description"),
           quantity=item.get("Standard_Quantity"),
           cost_price=item.get("Calculated_Cost_Price_Per_Unit"),
           net_amount=item.get("Net_Line_Amount"),
           batch_no=item.get("Batch_No"),
           hsn_code=item.get("HSN_Code") or "UNKNOWN", 
           mrp=item.get("MRP", 0.0)
    )
