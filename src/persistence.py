from src.normalization import parse_float
import os
import json
from src.utils.logging_config import get_logger
from src.services.embeddings import generate_embedding

logger = get_logger(__name__)

def upsert_user(driver, user_data: Dict[str, Any]):
    """
    Creates or updates a User node based on Google OAuth data.
    """
    query = """
    MERGE (u:User {email: $email})
    SET u.google_id = $google_id,
        u.name = $name,
        u.picture = $picture,
        u.updated_at = timestamp()
    RETURN u
    """
    with driver.session() as session:
        session.run(query, 
                    email=user_data.get("email"),
                    google_id=user_data.get("google_id"),
                    name=user_data.get("name"),
                    picture=user_data.get("picture"))

def ingest_invoice(driver, invoice_data: InvoiceExtraction, normalized_items: List[Dict[str, Any]], user_email: str, supplier_details: Dict[str, Any] = None):
    """
    Ingests invoice and line item data into Neo4j, scoped to a specific User.
    Also merges detailed Supplier information if available.
    """
    
    # Calculate Grand Total from line items to ensure consistency
    grand_total = sum(item.get("Net_Line_Amount", 0.0) for item in normalized_items)
    
    with driver.session() as session:
        # 1. Merge Invoice (Scoped to User)
        session.execute_write(_create_invoice_tx, invoice_data, grand_total, user_email)
        
        # 2. Merge Separate Supplier Node (Rich Data, Scoped to User)
        if supplier_details:
            # Ensure name matches the Invoice's supplier name for consistency
            supplier_name = invoice_data.Supplier_Name
            session.execute_write(_merge_supplier_tx, supplier_name, supplier_details, user_email)
        
    # 3. Process Line Items
        for raw_item, item in zip(invoice_data.Line_Items, normalized_items):
            session.execute_write(_create_line_item_tx, invoice_data.Invoice_No, item, raw_item, user_email)
            
        # 4. Save Invoice Example for RAG (Few-Shot)
        # Only if raw_text is available
        if invoice_data.raw_text:
            logger.info("Generating Vector Embedding for Invoice Example...")
            try:
                # Prepare JSON Payload (Full Extraction)
                # We save the verified extraction as the 'ground truth' for this text
                json_payload = invoice_data.model_dump_json() if hasattr(invoice_data, 'model_dump_json') else invoice_data.json()
                
                # Generate Embedding
                embedding = generate_embedding(invoice_data.raw_text)
                
                if embedding:
                    session.execute_write(
                        _create_invoice_example_tx, 
                        invoice_data.Supplier_Name, 
                        invoice_data.raw_text, 
                        json_payload, 
                        embedding
                    )
            except Exception as e:
                logger.error(f"Failed to save Invoice Example: {e}")

def _merge_supplier_tx(tx, name, details, user_email):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (s:Supplier {name: $name})
    
    // Create ownership if not exists
    MERGE (u)-[:OWNS]->(s)
    
    SET s.address = $address,
        s.gstin = $gstin,
        s.dl_no = $dl_no,
        s.phone = $phone,
        s.email = $email,
        s.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           name=name,
           address=details.get("Address"),
           gstin=details.get("GSTIN"),
           dl_no=details.get("DL_No"),
           phone=details.get("Phone_Number"),
           email=details.get("Email")
    )

def create_invoice_draft(driver, state: Dict[str, Any], user_email: str):
    """
    Creates a DRAFT invoice node in Neo4j, scoped to a User.
    Used for Staging before full confirmation.
    """
    global_mods = state.get("global_modifiers", {})
    invoice_no = global_mods.get("Invoice_No", "UNKNOWN")
    supplier = global_mods.get("Supplier_Name", "UNKNOWN")
    
    with driver.session() as session:
        session.execute_write(_create_draft_tx, invoice_no, supplier, state, user_email)
        
def _create_draft_tx(tx, invoice_no, supplier, state, user_email):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier})
    MERGE (u)-[:OWNS]->(i)
    
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
           user_email=user_email,
           invoice_no=invoice_no, 
           supplier=supplier,
           raw_state=state_json)

def _create_invoice_tx(tx, invoice_data: InvoiceExtraction, grand_total: float, user_email: str):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (i:Invoice {invoice_number: $invoice_no, supplier_name: $supplier_name})
    MERGE (u)-[:OWNS]->(i)
    
    ON CREATE SET 
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.created_at = timestamp()
    ON MATCH SET
        i.status = 'CONFIRMED',
        i.invoice_date = $invoice_date,
        i.grand_total = $grand_total,
        i.image_path = $image_path,
        i.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           invoice_no=invoice_data.Invoice_No, 
           supplier_name=invoice_data.Supplier_Name,
           invoice_date=invoice_data.Invoice_Date,
           grand_total=grand_total,
           image_path=invoice_data.image_path)

def _create_line_item_tx(tx, invoice_no: str, item: Dict[str, Any], raw_item: Any, user_email: str):
    query = """
    MATCH (u:User {email: $user_email})
    MATCH (u)-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    
    // 1. Merge Global Product (Shared Catalog)
    // Instead of User-Owned Product, we map to a Global Product based on name
    MERGE (gp:GlobalProduct {name: $standard_item_name})
    
    // 2. Merge HSN Node
    MERGE (h:HSN {code: $hsn_code})
    
    // 3. Create Line Item (Specific Variant / Instance)
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
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    MERGE (l)-[:BELONGS_TO_HSN]->(h)
    """
    
    tx.run(query,
           user_email=user_email,
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

def get_activity_log(driver, user_email: str):
    """
    Fetches the last 20 processed invoices for the dashboard history, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status = 'CONFIRMED'
    OPTIONAL MATCH (u)-[:OWNS]->(s:Supplier {name: i.supplier_name})
    RETURN i.invoice_number as invoice_number, 
           i.supplier_name as supplier_name, 
           i.created_at as created_at, 
           i.grand_total as total,
           i.image_path as image_path,
           s.gstin as supplier_gst,
           s.phone as supplier_phone,
           s.dl_no as supplier_dl,
           s.address as supplier_address
    ORDER BY i.created_at DESC LIMIT 20
    """
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

def get_inventory(driver, user_email: str):
    """
    Fetches aggregated inventory data for the dashboard, scoped to User.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)-[:CONTAINS]->(l:Line_Item)
    MATCH (l)-[:IS_VARIANT_OF]->(gp:GlobalProduct)
    RETURN gp.name as product_name, 
           sum(l.quantity) as total_quantity, 
           max(l.mrp) as mrp
    ORDER BY total_quantity DESC
    """
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        return [dict(record) for record in result]

def get_invoice_details(driver, invoice_no, user_email: str):
    """
    Fetches full invoice details and line items, checking User ownership.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice {invoice_number: $invoice_no})
    OPTIONAL MATCH (u)-[:OWNS]->(s:Supplier {name: i.supplier_name})
    OPTIONAL MATCH (i)-[:CONTAINS]->(l:Line_Item)
    OPTIONAL MATCH (l)-[:IS_VARIANT_OF]->(p:GlobalProduct)
    RETURN i, s, collect({
        line: l, 
        product: p 
    }) as items
    """
    with driver.session() as session:
        result = session.run(query, invoice_no=invoice_no, user_email=user_email).single()
        
    if not result:
        return None
        
    invoice_node = dict(result["i"])
    supplier_node = dict(result["s"]) if result["s"] else {}
    
    # Merge supplier info into invoice dict for convenience
    invoice_data = {**invoice_node}
    invoice_data["supplier_phone"] = supplier_node.get("phone")
    invoice_data["supplier_gst"] = supplier_node.get("gstin")
    invoice_data["supplier_address"] = supplier_node.get("address")
    invoice_data["supplier_dl"] = supplier_node.get("dl_no")
    
    line_items = []
    for item in result["items"]:
        l_node = dict(item["line"]) if item["line"] else {}
        p_node = dict(item["product"]) if item["product"] else {}
        
        # Construct flat item dict
        line_item = {
            **l_node,
            "product_name": p_node.get("name", l_node.get("raw_description", "Unknown"))
        }
        line_items.append(line_item)
        
    return {
        "invoice": invoice_data,
        "line_items": line_items
    }

def get_grouped_invoice_history(driver, user_email: str):
    """
    Fetches invoices grouped by Supplier for the History View.
    """
    query = """
    MATCH (u:User {email: $user_email})-[:OWNS]->(i:Invoice)
    WHERE i.status = 'CONFIRMED'
    
    // Group by Supplier Name
    WITH i.supplier_name as supplier_name, collect(i) as invoices
    
    // Calculate total spend per supplier
    // (Ensure grand_total is treated as float)
    WITH supplier_name, invoices, 
         reduce(msg = 0.0, inv in invoices | msg + coalesce(inv.grand_total, 0.0)) as total_spend
         
    RETURN supplier_name, total_spend, invoices
    ORDER BY total_spend DESC
    """
    
    data = []
    with driver.session() as session:
        result = session.run(query, user_email=user_email)
        
        for record in result:
            supplier_name = record["supplier_name"]
            total_spend = record["total_spend"]
            invoice_nodes = record["invoices"]
            
            # Format invoices list
            formatted_invoices = []
            for node in invoice_nodes:
                inv = dict(node)
                formatted_invoices.append({
                    "invoice_number": inv.get("invoice_number"),
                    "date": inv.get("invoice_date"),
                    "total": inv.get("grand_total"),
                    "image_path": inv.get("image_path") # Ensure we capture image path if stored on Invoice node
                })
                
            # Sort invoices by date (newest first)
            # Assuming date format is sortable or just rely on DB order if we added ORDER BY in collect (complex in one query)
            # Let's sort in python
            formatted_invoices.sort(key=lambda x: x.get("date") or "", reverse=True)
            
            data.append({
                "name": supplier_name,
                "total_spend": total_spend,
                "invoices": formatted_invoices
            })
            
    return data

def _create_invoice_example_tx(tx, supplier_name: str, raw_text: str, json_payload: str, embedding: List[float]):
    """
    Creates an InvoiceExample node linked to the Supplier.
    Stores the raw text, verified JSON, and the vector embedding.
    """
    query = """
    MATCH (s:Supplier {name: $supplier_name})
    
    CREATE (e:InvoiceExample {
        raw_text: $raw_text,
        json_payload: $json_payload,
        created_at: timestamp()
    })
    
    # Store embedding as a Vector property (Neo4j 5.x+)
    SET e.embedding = $embedding
    
    # Link to Supplier (One Supplier has many Examples)
    MERGE (s)-[:HAS_EXAMPLE]->(e)
    """
    tx.run(query, 
           supplier_name=supplier_name, 
           raw_text=raw_text, 
           json_payload=json_payload, 
           embedding=embedding)

def init_vector_index(driver):
    """
    Creates Vector Indexes for Invoice Examples and HSN Codes.
    Run this on startup.
    """
    # 1. Invoice Examples Index
    q1 = """
    CREATE VECTOR INDEX invoice_examples_index IF NOT EXISTS
    FOR (n:InvoiceExample)
    ON (n.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """
    
    # 2. HSN Vector Index
    q2 = """
    CREATE VECTOR INDEX hsn_vector_index IF NOT EXISTS
    FOR (n:HSN)
    ON (n.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """
    
    try:
        with driver.session() as session:
            session.run(q1)
            logger.info("Vector Index 'invoice_examples_index' initialization checked.")
            
            session.run(q2)
            logger.info("Vector Index 'hsn_vector_index' initialization checked.")
    except Exception as e:
        logger.error(f"Failed to create Vector Indexes: {e}")
