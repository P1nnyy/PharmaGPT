from typing import List, Dict, Any
from src.schemas import InvoiceExtraction

def ingest_invoice(driver, invoice_data: InvoiceExtraction, normalized_items: List[Dict[str, Any]], image_path: str = None):
    """
    Ingests invoice and line item data into Neo4j.
    """
    # Calculate Grand Total from line items to ensure consistency
    grand_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
    
    with driver.session() as session:
        # 1. Merge Invoice
        session.execute_write(_create_invoice_tx, invoice_data, grand_total, image_path)
        
    # 2. Process Line Items
        for raw_item, item in zip(invoice_data.Line_Items, normalized_items):
            session.execute_write(_create_line_item_tx, invoice_data.Invoice_No, item, raw_item)

def _create_invoice_tx(tx, invoice_data: InvoiceExtraction, grand_total: float, image_path: str = None):
    query = """
    // 1. Merge Supplier
    MERGE (s:Supplier {name: $supplier_name})
    
    // 2. Merge Invoice
    MERGE (i:Invoice {invoice_number: $invoice_no})
    ON CREATE SET 
        i.supplier_name = $supplier_name,
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.created_at = timestamp()
    ON MATCH SET
        i.supplier_name = $supplier_name,
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.updated_at = timestamp()
        
    // 3. Link Supplier -> Invoice
    MERGE (s)-[:ISSUED]->(i)
    """
    tx.run(query, 
           invoice_no=invoice_data.Invoice_No, 
           supplier_name=invoice_data.Supplier_Name,
           invoice_date=invoice_data.Invoice_Date,
           grand_total=grand_total,
           image_path=image_path)

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any):
    query = """
    MATCH (i:Invoice {invoice_number: $invoice_no})
    
    // 1. Merge Product (Standard Name)
    MERGE (p:Product {name: $standard_item_name})
    
    // 2. Merge HSN Node
    MERGE (h:HSN {code: $hsn_code})
    
    // 3. Find Last Price (Price Watchdog)
    WITH i, p, h
    OPTIONAL MATCH (p)<-[:REFERENCES]-(last:Line_Item)
    WITH i, p, h, last 
    ORDER BY last.created_at DESC LIMIT 1
    
    WITH i, p, h, last, 
         CASE 
            WHEN last IS NOT NULL AND $landing_cost > last.landing_cost THEN true 
            ELSE false 
         END AS is_price_hike
         
    // 4. Create Line Item
    CREATE (l:Line_Item {
        pack_size: $pack_size,
        quantity: $quantity,
        net_amount: $net_amount,
        batch_no: $batch_no,
        hsn_code: $hsn_code,
        mrp: $mrp,
        expiry_date: $expiry_date,
        landing_cost: $landing_cost,
        logic_note: $logic_note,
        is_price_hike: is_price_hike, 
        created_at: timestamp()
    })
    
    // 5. Connect Graph
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
           landing_cost=item.get("Final_Unit_Cost", 0.0), 
           logic_note=item.get("Logic_Note", "N/A")
    )

def get_last_landing_cost(driver, product_name: str) -> float:
    """
    Helper to fetch the last known landing cost for a product.
    """
    query = """
    MATCH (p:Product {name: $name})<-[:REFERENCES]-(l:Line_Item)
    RETURN l.landing_cost as cost 
    ORDER BY l.created_at DESC LIMIT 1
    """
    try:
        with driver.session() as session:
            result = session.run(query, name=product_name).single()
            if result:
                return float(result["cost"] or 0.0)
    except Exception:
        pass
    return 0.0

def check_inflation_on_analysis(driver, normalized_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Price Watchdog (Read-Only Check).
    """
    if not driver:
        return normalized_items

    for item in normalized_items:
        name = item.get("Standard_Item_Name")
        current_price = item.get("Final_Unit_Cost", 0.0)
        
        if name:
            last_price = get_last_landing_cost(driver, name)
            if last_price > 0 and current_price > last_price:
                item["is_price_hike"] = True
                item["last_known_price"] = last_price 
            else:
                item["is_price_hike"] = False
        else:
            item["is_price_hike"] = False
                
    return normalized_items
