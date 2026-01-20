import sys
import os
import requests
import json
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from src.services.database import get_db_driver, connect_db, close_db

API_URL = "http://localhost:5001"
USER_EMAIL = "pranav@pharmagpt.co"

def verify_rename_flow():
    connect_db()
    driver = get_db_driver()
    
    print("1. Setup: Clean up test data.")
    with driver.session() as session:
        session.run("MATCH (gp:GlobalProduct) WHERE gp.name STARTS WITH 'TEST-RENAME' DETACH DELETE gp")
        session.run("MATCH (a:ProductAlias) WHERE a.raw_name STARTS WITH 'TEST-RENAME' DETACH DELETE a")
        session.run("MERGE (:User {email: $email})", email=USER_EMAIL)

    print("2. Create Initial Product 'TEST-RENAME-OLD'")
    # Direct DB creation to simulate existing state
    with driver.session() as session:
        session.run("""
        MATCH (u:User {email: $email})
        MERGE (gp:GlobalProduct {name: 'TEST-RENAME-OLD'})
        MERGE (u)-[:MANAGES]->(gp)
        """, email=USER_EMAIL)
        
    print("3. Call API to Rename 'TEST-RENAME-OLD' -> 'TEST-RENAME-NEW'")
    # Assuming we have a way to mock auth or bypass it? 
    # The API requires token. I might need to mock or just test the persistence function directly?
    # Testing endpoints requires running server + auth.
    # Let's test the persistence function directly to be faster and reliable without token setup.
    
    from src.domain.persistence import rename_product_with_alias, link_product_alias
    
    rename_product_with_alias(driver, USER_EMAIL, "TEST-RENAME-OLD", "TEST-RENAME-NEW")
    
    print("4. Verify Rename Graph")
    with driver.session() as session:
        # Check Alias -> New
        q = "MATCH (a:ProductAlias {raw_name: 'TEST-RENAME-OLD'})-[:MAPS_TO]->(gp:GlobalProduct {name: 'TEST-RENAME-NEW'}) RETURN count(a) as cnt"
        cnt = session.run(q).single()["cnt"]
        if cnt == 1:
            print("   SUCCESS: Old name became Alias linked to New Name.")
        else:
            print(f"   FAILURE: Rename graph incorrect. cnt={cnt}")
            
        # Check Old Node gone (except as alias node, which is distinct label)
        q2 = "MATCH (gp:GlobalProduct {name: 'TEST-RENAME-OLD'}) RETURN count(gp) as cnt"
        cnt2 = session.run(q2).single()["cnt"]
        if cnt2 == 0:
             print("   SUCCESS: Old GlobalProduct node renamed (gone).")
        else:
             print("   FAILURE: Old GlobalProduct still exists.")

    print("5. Test Alias Linking (Review Queue Logic)")
    # Link "TEST-RENAME-RAW" to "TEST-RENAME-NEW"
    link_product_alias(driver, USER_EMAIL, "TEST-RENAME-NEW", "TEST-RENAME-RAW")
    
    with driver.session() as session:
        q3 = "MATCH (a:ProductAlias {raw_name: 'TEST-RENAME-RAW'})-[:MAPS_TO]->(gp:GlobalProduct {name: 'TEST-RENAME-NEW'}) RETURN count(a) as cnt"
        cnt3 = session.run(q3).single()["cnt"]
        if cnt3 == 1:
            print("   SUCCESS: Manual Alias linked correctly.")
        else:
            print("   FAILURE: Manual Alias link failed.")
            
    close_db()

if __name__ == "__main__":
    verify_rename_flow()
