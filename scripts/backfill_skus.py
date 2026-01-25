
from src.services.database import get_db_driver
from src.domain.persistence import _generate_sku, init_db_constraints
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

def backfill_skus():
    driver = get_db_driver()
    if not driver:
        logger.error("No DB Driver")
        return

    # 1. Init Constraints first
    init_db_constraints(driver)
    
    # 2. Find all Products without SKU
    query = """
    MATCH (p:GlobalProduct)
    WHERE p.item_code IS NULL OR p.item_code = ''
    RETURN p.name as name
    """
    
    with driver.session() as session:
        result = session.run(query)
        products = [record["name"] for record in result]
        
    logger.info(f"Found {len(products)} products missing SKUs.")
    
    count = 0
    # 3. Process each (Transactionally generate and assign)
    for name in products:
        try:
            with driver.session() as session:
                # Generate SKU
                sku = session.execute_write(_generate_sku, name)
                
                # Assign to Product
                update_query = """
                MATCH (p:GlobalProduct {name: $name})
                SET p.item_code = $sku
                """
                session.run(update_query, name=name, sku=sku)
                print(f"Assigning {sku} -> {name}")
                count += 1
        except Exception as e:
            logger.error(f"Failed to backfill {name}: {e}")
            
    logger.info(f"Backfill Complete. Updated {count} products.")

if __name__ == "__main__":
    backfill_skus()
