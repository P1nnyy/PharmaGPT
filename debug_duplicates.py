
from src.services.database import get_db_driver

def check_duplicates():
    driver = get_db_driver()
    if not driver:
        print("Driver not available")
        return

    # Query for products that look like ONDERO or GLIPTAGREAT
    query = """
    MATCH (gp:GlobalProduct)
    WHERE toLower(gp.name) CONTAINS 'ondero' OR toLower(gp.name) CONTAINS 'glipta'
    RETURN gp.name, gp.is_verified, gp.needs_review
    """
    
    with driver.session() as session:
        result = session.run(query)
        print(f"{'Name':<40} | {'Verified':<10} | {'Review':<10}")
        print("-" * 70)
        for record in result:
            print(f"{record['gp.name']:<40} | {str(record['gp.is_verified']):<10} | {str(record['gp.needs_review']):<10}")

if __name__ == "__main__":
    check_duplicates()
