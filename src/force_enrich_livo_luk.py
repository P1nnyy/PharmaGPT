from src.services.database import get_db_driver
from src.services.enrichment_agent import EnrichmentAgent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("force_enrich")

USER_EMAIL = "pranavgupta1638@gmail.com"
PRODUCT_NAME = "LIVO-LUK SOLUTION 200ML"

def force_enrich():
    driver = get_db_driver()
    agent = EnrichmentAgent()
    
    print(f"Force Enriching: {PRODUCT_NAME}")
    
    # Call Agent
    result = agent.enrich_product(PRODUCT_NAME)
    print(f"Agent Result: {result}")
    
    if not result.get("manufacturer") and not result.get("salt_composition"):
        print("Enrichment Failed (Empty Data).")
        return

    # Update DB
    update_query = """
    MATCH (u:User {email: $email})-[:MANAGES]->(gp:GlobalProduct {name: $name})
    SET gp.manufacturer = $manufacturer,
        gp.salt_composition = $salt,
        gp.category = $category,
        gp.is_verified = true,
        gp.is_enriched = true,
        gp.updated_at = timestamp()
    """
    
    print("Updating DB...")
    with driver.session() as session:
        session.run(update_query, 
                    email=USER_EMAIL,
                    name=PRODUCT_NAME,
                    manufacturer=result.get("manufacturer"),
                    salt=result.get("salt_composition"),
                    category=result.get("category"))
                    
    print("Success! Database Updated.")

if __name__ == "__main__":
    force_enrich()
