
import os
import sys

sys.path.append(os.getcwd())

from src.services.database import get_db_driver

TARGET_EMAIL = "pranavgupta1638@gmail.com"

def migrate_orphans():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    query = """
    MATCH (u:User {email: $email})
    MATCH (gp:GlobalProduct)
    WHERE NOT (:User)-[:MANAGES]->(gp)
    MERGE (u)-[:MANAGES]->(gp)
    RETURN count(gp) as migrated_count
    """

    print(f"Migrating orphaned products to user: {TARGET_EMAIL}...")
    
    with driver.session() as session:
        result = session.run(query, email=TARGET_EMAIL)
        count = result.single()["migrated_count"]
        print(f"Successfully linked {count} products to {TARGET_EMAIL}.")

if __name__ == "__main__":
    migrate_orphans()
