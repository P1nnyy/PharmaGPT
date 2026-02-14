from src.services.database import get_db_driver

USER_EMAIL = "pranavgupta1638@gmail.com"

def count_missing():
    driver = get_db_driver()
    query = """
    MATCH (u:User {email: $email})-[:MANAGES]->(gp:GlobalProduct)
    WHERE gp.manufacturer IS NULL
    RETURN count(gp) as count, collect(gp.name) as names
    """
    with driver.session() as session:
        result = session.run(query, email=USER_EMAIL).single()
        print(f"Total Missing Manufacturer: {result['count']}")
        print(f"Names: {result['names'][:10]}")

if __name__ == "__main__":
    count_missing()
