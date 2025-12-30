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
    # Prepare Metadata Params
    meta = invoice_data.metadata
    
    # Use explicit fallback vars
    _address = meta.Address if meta else None
    _phone_pri = meta.Phone_Primary if meta else invoice_data.Supplier_Phone
    _phone_sec = meta.Phone_Secondary if meta else None
    _email = meta.Email if meta else None
    _gst = meta.GSTIN if meta else invoice_data.Supplier_GST
    _dl_20b = meta.Drug_License_20B if meta else None
    _dl_21b = meta.Drug_License_21B if meta else None

    query = """
    // 1. Merge Supplier (Strict Upsert)
    MERGE (s:Supplier {name: $supplier_name})
    ON CREATE SET 
        s.phone = $supplier_phone,
        s.phone_secondary = $phone_secondary,
        s.gst = $supplier_gst,
        s.address = $address,
        s.email = $email,
        s.dl_20b = $dl_20b,
        s.dl_21b = $dl_21b,
        s.created_at = timestamp()
    ON MATCH SET 
        // Only overwrite if new data is present (COALESCE preferred)
        s.phone = COALESCE($supplier_phone, s.phone),
        s.phone_secondary = COALESCE($phone_secondary, s.phone_secondary),
        s.gst = COALESCE($supplier_gst, s.gst),
        s.address = COALESCE($address, s.address),
        s.email = COALESCE($email, s.email),
        s.dl_20b = COALESCE($dl_20b, s.dl_20b),
        s.dl_21b = COALESCE($dl_21b, s.dl_21b),
        s.updated_at = timestamp()
    
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
           supplier_phone=_phone_pri,
           phone_secondary=_phone_sec,
           supplier_gst=_gst,
           address=_address,
           email=_email,
           dl_20b=_dl_20b,
           dl_21b=_dl_21b,
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

def get_recent_activity(driver) -> List[Dict[str, Any]]:
    """
    Fetches a flat list of all invoices for the timeline view.
    Sorted by created_at DESC (newest first).
    """
    query = """
    MATCH (i:Invoice)
    OPTIONAL MATCH (s:Supplier)-[:ISSUED]->(i)
    RETURN 
        i.invoice_number as invoice_number,
        i.invoice_date as date,
        i.grand_total as total,
        i.status as status,
        i.image_path as image_path,
        s.name as supplier_name,
        s.phone as supplier_phone,
        s.gst as supplier_gst,
        i.created_at as created_at
    ORDER BY i.created_at DESC
    LIMIT 50
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            activity_log = []
            for record in result:
                activity_log.append({
                    "invoice_number": record["invoice_number"],
                    "date": record["date"],
                    "total": record["total"],
                    "status": record["status"],
                    "image_path": record["image_path"],
                    "supplier_name": record["supplier_name"] or "Unknown",
                    "supplier_phone": record["supplier_phone"],
                    "supplier_gst": record["supplier_gst"],
                    "created_at": record["created_at"]
                })
            return activity_log
    except Exception as e:
        print(f"Error fetching recent activity: {e}")
        return []
