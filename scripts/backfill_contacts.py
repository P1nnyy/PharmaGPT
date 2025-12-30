import asyncio
import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables FIRST
load_dotenv()

from src.workflow.nodes.contact_hunter import extract_supplier_details

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

async def process_suppliers():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j.")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return

    query = """
    MATCH (i:Invoice)<-[:ISSUED]-(s:Supplier)
    WHERE s.phone IS NULL OR s.gst IS NULL
    RETURN i.image_path as image_path, s.name as supplier_name, elementId(s) as s_id
    """
    
    with driver.session() as session:
        results = list(session.run(query))
        
    print(f"Found {len(results)} invoices to scan for contact info.")
    
    for record in results:
        image_path_Rel = record["image_path"]
        supplier_name = record["supplier_name"]
        
        # Convert /static/invoices/... to uploads/invoices/...
        if not image_path_Rel:
            continue
            
        local_path = image_path_Rel.lstrip("/").replace("static/", "uploads/")
        
        if not os.path.exists(local_path):
            print(f"File not found: {local_path}")
            continue
            
        print(f"Scanning {local_path} for {supplier_name}...")
        
        try:
            contact_info = await extract_supplier_details(local_path)
            
            phone = contact_info.get("Supplier_Phone")
            gst = contact_info.get("Supplier_GST")
            
            if phone or gst:
                print(f"Updating {supplier_name}: Phone={phone}, GST={gst}")
                update_query = """
                MATCH (s:Supplier {name: $name})
                SET s.phone = $phone, s.gst = $gst, s.updated_at = timestamp()
                """
                with driver.session() as session:
                     session.run(update_query, name=supplier_name, phone=phone, gst=gst)
            else:
                print(f"No contact info found for {supplier_name}.")
                
        except Exception as e:
            print(f"Error processing {supplier_name}: {e}")

    driver.close()
    print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(process_suppliers())
