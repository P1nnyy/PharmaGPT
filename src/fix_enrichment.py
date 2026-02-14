
from dotenv import load_dotenv
import os
import json
import requests
from src.utils.logging_config import get_logger
from src.services.database import get_db_driver
from src.services.enrichment_agent import EnrichmentAgent

load_dotenv()
# Force simple logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_enrichment")

USER_EMAIL = "pranavgupta1638@gmail.com"

def fix_enrichment():
    driver = get_db_driver()
    
    # Test Connectivity
    try:
        print("Testing 1mg connectivity...")
        r = requests.get("https://www.1mg.com", timeout=5)
        print(f"1mg Status: {r.status_code}")
    except Exception as e:
        print(f"1mg Connectivity Failed: {e}")
        return

    agent = EnrichmentAgent()
    
    # query to find products managed by user THAT HAVE NO MANUFACTURER
    find_query = """
    MATCH (u:User {email: $email})-[:MANAGES]->(gp:GlobalProduct)
    WHERE gp.manufacturer IS NULL
    RETURN gp.name, gp.hsn_code
    """
    
    with driver.session() as session:
        records = session.run(find_query, email=USER_EMAIL).data()
        
    print(f"Found {len(records)} products needing enrichment.")
    
    for rec in records:
        product_name = rec['gp.name']
        print(f"Processing: {product_name}...")
        
        try:
            # Re-run enrichment
            # Note: The agent uses internal threading. If that hangs, we'll see it here.
            print("  - Calling agent.enrich_product...")
            result = agent.enrich_product(product_name)
            print("  - Agent returned.")
            
            if result.get("error"):
                print(f"  Error: {result['error']}")
                continue

            # ---------------------------------------------------------
            # Fix: Update Packaging Unit based on Enriched Category
            # ---------------------------------------------------------
            from src.domain.normalization.text import structure_packaging_hierarchy
            
            # Since this is a recovery script, we might not have 'local_pack_size' easily available 
            # unless we query it or assume it's ambiguous. 
            # But structure_packaging_hierarchy handles None/Empty by defaulting.
            # However, for LUBIMOIST, the pack size IS likely ambiguous or "1".
            pack_info = structure_packaging_hierarchy(None, enrichment_category=result.get("category"))
            
            if pack_info and pack_info.get("base_unit"):
                new_base_unit = pack_info.get("base_unit")
                print(f"  > Correcting Base Unit -> {new_base_unit}")

            # Check validity
            if not result.get("manufacturer") and not result.get("salt_composition"):
                print(f"  > Empty result for {product_name}. Skipping DB update.")
                continue

            # Update DB
            update_query = """
            MATCH (u:User {email: $email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
            SET gp.manufacturer = $manufacturer,
                gp.salt_composition = $salt,
                gp.category = $category,
                gp.is_verified = true,
                gp.is_enriched = true,
                gp.base_unit = CASE WHEN $base_unit IS NOT NULL THEN $base_unit ELSE gp.base_unit END,
                gp.unit_name = CASE WHEN $base_unit IS NOT NULL THEN $base_unit ELSE gp.unit_name END,
                gp.updated_at = timestamp()
            """
            
            print("  - Updating DB...")
            with driver.session() as session:
                session.run(update_query, 
                            email=USER_EMAIL,
                            name=product_name,
                            manufacturer=result.get("manufacturer"),
                            salt=result.get("salt_composition"),
                            category=result.get("category"),
                            base_unit=new_base_unit)
                            
            print(f"  Success! Set Manufacturer: {result.get('manufacturer')}")
            
        except Exception as e:
            print(f"  Exception for {product_name}: {e}")

if __name__ == "__main__":
    fix_enrichment()
