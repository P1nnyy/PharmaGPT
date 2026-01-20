import sys
import os
import uuid
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from src.services.database import get_db_driver, connect_db, close_db
from src.domain.persistence import ingest_invoice
from src.domain.schemas import InvoiceExtraction

USER_EMAIL = "pranav@pharmagpt.co"
MASTER_PRODUCT = "Actirom"
PACK_SIZE_1 = "10s"
PACK_SIZE_2 = "20s"

def verify_packaging_variant():
    connect_db()
    driver = get_db_driver()
    
    print(f"1. Setup: Ensure Master Product '{MASTER_PRODUCT}' and User exist.")
    with driver.session() as session:
        session.run("MERGE (:GlobalProduct {name: $name})", name=MASTER_PRODUCT)
        session.run("MERGE (:User {email: $email, name: 'Test User'})", email=USER_EMAIL)

    print(f"2. Ingest Item 1: '{MASTER_PRODUCT}' with Pack Size '{PACK_SIZE_1}'")
    inv1 = InvoiceExtraction(
        Invoice_No=f"TEST-PACK-{uuid.uuid4().hex[:6]}",
        Invoice_Date="2024-01-20",
        Supplier_Name="Test Supplier",
        Stated_Grand_Total=100.0,
        Line_Items=[{"Description": "Raw 10s", "Amount": "100.00", "Product": "Actirom"}],
        raw_text="Test"
    )
    items1 = [{
        "Standard_Item_Name": MASTER_PRODUCT,
        "Net_Line_Amount": 100.0,
        "Standard_Quantity": 10,
        "Pack_Size_Description": PACK_SIZE_1,
        "Product": MASTER_PRODUCT # For alias lookup context if needed
    }]
    ingest_invoice(driver, inv1, items1, USER_EMAIL)
    
    print(f"3. Ingest Item 2: '{MASTER_PRODUCT}' with Pack Size '{PACK_SIZE_2}'")
    inv2 = InvoiceExtraction(
        Invoice_No=f"TEST-PACK-{uuid.uuid4().hex[:6]}",
        Invoice_Date="2024-01-20",
        Supplier_Name="Test Supplier",
        Stated_Grand_Total=200.0,
        Line_Items=[{"Description": "Raw 20s", "Amount": "200.00", "Product": "Actirom"}],
        raw_text="Test"
    )
    items2 = [{
        "Standard_Item_Name": MASTER_PRODUCT,
        "Net_Line_Amount": 200.0,
        "Standard_Quantity": 20,
        "Pack_Size_Description": PACK_SIZE_2,
        "Product": MASTER_PRODUCT
    }]
    ingest_invoice(driver, inv2, items2, USER_EMAIL)
    
    print("4. Verifying Graph Structure...")
    with driver.session() as session:
        # Check Variants linked to Master
        query = """
        MATCH (gp:GlobalProduct {name: $name})-[:HAS_VARIANT]->(pv:PackagingVariant)
        RETURN pv.pack_size as size, pv.product_name as p_name
        """
        result = session.run(query, name=MASTER_PRODUCT)
        variants = [record["size"] for record in result]
        
        print(f"   Found Variants for {MASTER_PRODUCT}: {variants}")
        
        if PACK_SIZE_1 in variants and PACK_SIZE_2 in variants:
            print("   SUCCESS: Both variants created and linked to Master.")
        else:
            print("   FAILURE: Missing variants.")

        # Check Line Item linkage
        query_li = """
        MATCH (l:Line_Item)-[:IS_PACKAGING_VARIANT]->(pv:PackagingVariant {pack_size: $size})
        WHERE pv.product_name = $name
        RETURN count(l) as cnt
        """
        cnt1 = session.run(query_li, size=PACK_SIZE_1, name=MASTER_PRODUCT).single()["cnt"]
        cnt2 = session.run(query_li, size=PACK_SIZE_2, name=MASTER_PRODUCT).single()["cnt"]
        
        print(f"   Line Items linked to {PACK_SIZE_1}: {cnt1}")
        print(f"   Line Items linked to {PACK_SIZE_2}: {cnt2}")
        
        if cnt1 >= 1 and cnt2 >= 1:
            print("   SUCCESS: Line Items correctly linked to specific variants.")
        else:
            print("   FAILURE: Line Item linkage broken.")
            
            # DEBUG DUMP
            print("\n--- DEBUG DUMP ---")
            debug_q = """
            MATCH (gp:GlobalProduct {name: $name})
            OPTIONAL MATCH (gp)-[:HAS_VARIANT]->(pv:PackagingVariant)
            OPTIONAL MATCH (pv)<-[r]-(l:Line_Item)
            RETURN pv, r, l
            """
            recs = session.run(debug_q, name=MASTER_PRODUCT).data()
            for r in recs:
                print(r)
                
            print("\n--- LINE ITEM RELIGIONS ---")
            li_q = """
            MATCH (i:Invoice)-[:CONTAINS]->(l:Line_Item)
            MATCH (l)-[r]->(target)
            RETURN type(r), target
            """
            recs = session.run(li_q).data()
            for r in recs:
                 print(r)

    close_db()

if __name__ == "__main__":
    verify_packaging_variant()
