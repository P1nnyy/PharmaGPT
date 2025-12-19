import os
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load .env
load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

if not uri or not user or not password:
    print("❌ Critical: Missing Neo4j credentials in .env")
    sys.exit(1)

print(f"📡 Connecting to Cloud DB: {uri}")

def verify_and_init(driver):
    with driver.session() as session:
        # 1. Check & Create Constraints
        print("🔍 Checking Schema Constraints...")
        
        # Unique Invoice Number
        try:
            session.run("CREATE CONSTRAINT unique_invoice IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoice_number IS UNIQUE")
            print("   ✅ Constraint 'unique_invoice' (Invoice.invoice_number) ensured.")
        except Exception as e:
            print(f"   ⚠️ Could not set Invoice constraint (might verify manually): {e}")

        # Unique Product Name
        try:
            session.run("CREATE CONSTRAINT unique_product IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE")
            print("   ✅ Constraint 'unique_product' (Product.name) ensured.")
        except Exception as e:
            print(f"   ⚠️ Could not set Product constraint: {e}")

        # 2. Write Test
        print("\n📝 Testing Write Access...")
        test_id = "cloud_ping_test"
        try:
            # Create dummy
            session.run("CREATE (:CloudTest {id: $id, timestamp: timestamp()})", id=test_id)
            # Verify and Delete
            result = session.run("MATCH (n:CloudTest {id: $id}) DETACH DELETE n RETURN count(n) as del_count", id=test_id)
            count = result.single()["del_count"]
            
            if count == 1:
                print("   ✅ Write & Delete confirmed.")
            else:
                print("   ⚠️ Write Test Inconclusive (Delete count != 1).")
        except Exception as e:
            print(f"   ❌ Write Failed: {e}")
            sys.exit(1)

    print("\n✅ Cloud Ready")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    verify_and_init(driver)
    driver.close()
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Connection or Init Failed: {e}")
    sys.exit(1)
