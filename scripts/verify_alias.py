import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import get_db_driver, connect_db, close_db
from src.domain.persistence import link_product_alias, ingest_invoice
from src.domain.schemas import InvoiceExtraction

# Mock Data
USER_EMAIL = "pranav@pharmagpt.co" # Change if needed, should match existing user
MASTER_PRODUCT = "Paracetamol-500"
ALIAS_NAME = "Para-500-Tab"

def verify_alias_system():
    connect_db()
    driver = get_db_driver()
    
    print(f"1. Creating Master Product '{MASTER_PRODUCT}' and User '{USER_EMAIL}'...")
    with driver.session() as session:
        session.run("MERGE (:GlobalProduct {name: $name})", name=MASTER_PRODUCT)
        session.run("MERGE (:User {email: $email, name: 'Test User'})", email=USER_EMAIL)
        
    print(f"2. Linking Alias '{ALIAS_NAME}' -> '{MASTER_PRODUCT}'...")
    link_product_alias(driver, USER_EMAIL, MASTER_PRODUCT, ALIAS_NAME)
    
    print("3. Simulating Ingestion with Alias Name...")
    # Create dummy invoice data
    invoice_data = InvoiceExtraction(
        Invoice_No="TEST-ALIAS-001",
        Invoice_Date="2024-01-20",
        Supplier_Name="Test Supplier",
        Stated_Grand_Total=100.0,
        Line_Items=[{"Description": "Raw Description", "Amount": "100.00", "Product": "Test Product"}],
        raw_text="Test"
    )
    
    # Normalized item uses the ALIAS name
    normalized_items = [{
        "Standard_Item_Name": ALIAS_NAME, 
        "Net_Line_Amount": 100.0,
        "Standard_Quantity": 10,
        "Pack_Size_Description": "1x10",
        "MRP": 20.0,
        "HSN_Code": "3004"
    }]
    
    ingest_invoice(driver, invoice_data, normalized_items, USER_EMAIL)
    
    print("4. Verifying Graph Structure...")
    with driver.session() as session:
        query = """
        MATCH (i:Invoice {invoice_number: 'TEST-ALIAS-001'})-[:CONTAINS]->(l:Line_Item)
        MATCH (l)-[:IS_VARIANT_OF]->(p:GlobalProduct)
        RETURN p.name as mapped_name
        """
        result = session.run(query).single()
        
        if result:
            mapped = result["mapped_name"]
            print(f"   Input Name: {ALIAS_NAME}")
            print(f"   Mapped Product: {mapped}")
            
            if mapped == MASTER_PRODUCT:
                print("   SUCCESS: Alias resolved correctly!")
            else:
                print(f"   FAILURE: Mapped to {mapped}, expected {MASTER_PRODUCT}")
        else:
            print("   FAILURE: No Line Item found.")

    close_db()

if __name__ == "__main__":
    verify_alias_system()
