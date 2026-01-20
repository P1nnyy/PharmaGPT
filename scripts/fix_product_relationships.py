from src.services.database import get_db_driver

def fix_relationships():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    email = "pranavgupta1638@gmail.com"

    query = """
    MATCH (u:User {email: $email})-[:OWNS]->(i:Invoice)-[:CONTAINS]->(l:Line_Item)
    MATCH (l)-[:IS_VARIANT_OF]->(gp:GlobalProduct)
    MERGE (u)-[:MANAGES]->(gp)
    RETURN count(distinct gp) as linked_products
    """
    
    with driver.session() as session:
        result = session.run(query, email=email).single()
        print(f"Linked {result['linked_products']} products to user {email}")

if __name__ == "__main__":
    fix_relationships()
