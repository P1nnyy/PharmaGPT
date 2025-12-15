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

def create_invoice_draft(driver, state: Dict[str, Any]):
    """
    Creates a DRAFT invoice node in Neo4j.
    Used for Staging before full confirmation.
    """
    global_mods = state.get("global_modifiers", {})
    invoice_no = global_mods.get("Invoice_No", "UNKNOWN")
    supplier = global_mods.get("Supplier_Name", "UNKNOWN")
    
    with driver.session() as session:
        session.execute_write(_create_draft_tx, invoice_no, supplier, state)
        
def _create_draft_tx(tx, invoice_no, supplier, state):
    query = """
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier})
    ON CREATE SET 
        i.status = 'DRAFT',
        i.created_at = timestamp(),
        i.raw_state = $raw_state
    ON MATCH SET
        i.status = 'DRAFT',  // Reset to draft if exists
        i.updated_at = timestamp(),
        i.raw_state = $raw_state
    """
    # Serialize state partially if needed, but neo4j can store strings
    import json
    state_json = json.dumps(state.get("final_output", {}), default=str)
    
    tx.run(query, 
           invoice_no=invoice_no, 
           supplier=supplier,
           raw_state=state_json)

def _create_invoice_tx(tx, invoice_data: InvoiceExtraction, grand_total: float):
    query = """
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier_name})
    ON CREATE SET 
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.created_at = timestamp()
    ON MATCH SET
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
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
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note
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
           net_amount=item.get("Net_Line_Amount"),
           batch_no=item.get("Batch_No"),
           hsn_code=item.get("HSN_Code") or "UNKNOWN", 
           mrp=item.get("MRP", 0.0),
           expiry_date=item.get("Expiry_Date"),
           landing_cost=item.get("Final_Unit_Cost", 0.0), # Updated Mapping
           logic_note=item.get("Logic_Note", "N/A")
    )
