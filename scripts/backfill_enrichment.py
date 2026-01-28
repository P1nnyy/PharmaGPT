import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.database import get_db_driver
from src.services.enrichment_agent import EnrichmentAgent
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

async def backfill_products():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to database.")
        return

    agent = EnrichmentAgent()

    # Fetch products that need enrichment
    # criteria: manufacturer is null or "Unknown"
    query = """
    MATCH (gp:GlobalProduct)
    WHERE gp.name = 'ONDERO MET 2.5/1000 M'
    RETURN gp.name as name
    """
    
    products_to_enrich = []
    with driver.session() as session:
        result = session.run(query)
        products_to_enrich = [record["name"] for record in result]
    
    print(f"Found {len(products_to_enrich)} products to enrich.")

    for product_name in products_to_enrich:
        print(f"Enriching: {product_name}...")
        try:
            # Synchronous call since agent might be sync or if raw requests
            # Check agent signature. In `products.py` it's called as `enrichment_agent.enrich_product(q)` which seems sync.
            result = agent.enrich_product(product_name)
            
            if result.get("error"):
                print(f"  Skipping {product_name}: {result['error']}")
                continue

            # Update DB
            update_query = """
            MATCH (gp:GlobalProduct {name: $name})
            SET gp.manufacturer = $manufacturer,
                gp.salt_composition = $salt,
                gp.category = $category,
                gp.is_verified = true,
                gp.updated_at = timestamp()
            """
            
            with driver.session() as session:
                session.run(update_query, 
                            name=product_name,
                            manufacturer=result.get("manufacturer"),
                            salt=result.get("salt_composition"),
                            category=result.get("category"))
            
            print(f"  Updated {product_name}: {result.get('manufacturer')} | {result.get('category')}")

        except Exception as e:
            print(f"  Failed to enrich {product_name}: {e}")

if __name__ == "__main__":
    asyncio.run(backfill_products())
