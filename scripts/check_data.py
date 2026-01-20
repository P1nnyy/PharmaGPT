from src.services.database import get_db_driver

def check_data():
    driver = get_db_driver()
    if not driver:
        print("Failed to connect to DB")
        return

    with driver.session() as session:
        # Check Users
        print("\n--- Users ---")
        users = session.run("MATCH (u:User) RETURN u.email, u.name")
        for r in users:
            print(f"User: {r['u.email']} ({r['u.name']})")

        # Check Products
        print("\n--- Global Products (Top 10) ---")
        products = session.run("MATCH (gp:GlobalProduct) RETURN gp.name, gp.hsn_code LIMIT 10")
        count = 0
        for r in products:
            count += 1
            print(f"Product: {r['gp.name']}")
        print(f"Total shown: {count}")

        # Check Relationships
        print("\n--- User -> MANAGES -> Product ---")
        rels = session.run("MATCH (u:User)-[:MANAGES]->(gp:GlobalProduct) RETURN u.email, count(gp) as product_count")
        for r in rels:
            print(f"User {r['u.email']} manages {r['product_count']} products")

if __name__ == "__main__":
    check_data()
