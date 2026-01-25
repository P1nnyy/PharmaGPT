
from src.services.database import get_db_driver

def fix_data():
    driver = get_db_driver()
    if not driver:
         return
         
    query = """
    MATCH (p:GlobalProduct {name: 'ONDERO MET 2.5/1000 M'})
    SET p.hsn_code = '30049099',
        p.tax_rate = 5.0
    RETURN p
    """
    
    with driver.session() as session:
        session.run(query)
        print("Fixed ONDERO MET data: HSN -> 30049099, Tax -> 5.0%")

if __name__ == "__main__":
    fix_data()
