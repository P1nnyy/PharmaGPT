
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())

from src.services.database import get_db_driver

# Data to inject
PRODUCT_NAME = "ACITROM-2MG-30TABS"
MOCK_INVOICE_NO = "INV-DEBUG-001"
MOCK_SUPPLIER = "MAHAJAN MEDICOS"
HSN_CODE = "300490" # Common pharma HSN
TAX_RATE = 12.0

def fix_acitrom():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    query = """
    MATCH (u:User {email: 'pranavgupta1638@gmail.com'})
    MERGE (gp:GlobalProduct {name: $name})
    
    // 1. Update Global Product Data (Fix missing HSN/Tax)
    SET gp.hsn_code = $hsn_code,
        gp.tax_rate = $tax_rate,
        gp.updated_at = timestamp()
        
    // 2. Create Mock Invoice
    MERGE (i:Invoice {invoice_id: 'debug-acitrom-inv-01'})
    ON CREATE SET
        i.invoice_number = $invoice_no,
        i.supplier_name = $supplier,
        i.invoice_date = $date,
        i.grand_total = 450.00,
        i.status = 'CONFIRMED',
        i.created_at = timestamp()
    MERGE (u)-[:OWNS]->(i)
    
    // 3. Create Line Item
    CREATE (l:Line_Item {
        quantity: 10,
        pack_size: '1x30',
        net_amount: 450.00,
        mrp: 65.00,
        batch_no: 'BATCH123',
        expiry_date: '12/26',
        hsn_code: $hsn_code
    })
    
    // 4. Link Everything
    MERGE (i)-[:CONTAINS]->(l)
    MERGE (l)-[:IS_VARIANT_OF]->(gp)
    
    RETURN gp.name, i.invoice_number, l.net_amount
    """
    
    with driver.session() as session:
        result = session.run(query, 
                             name=PRODUCT_NAME,
                             hsn_code=HSN_CODE,
                             tax_rate=TAX_RATE,
                             invoice_no=MOCK_INVOICE_NO,
                             supplier=MOCK_SUPPLIER,
                             date=datetime.now().strftime("%d-%m-%Y"))
        rec = result.single()
        print(f"✅ Fixed Data for: {rec['gp.name']}")
        print(f"   - Linked to Invoice: {rec['i.invoice_number']}")

if __name__ == "__main__":
    fix_acitrom()
