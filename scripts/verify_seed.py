import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.services.database import get_db_driver

def verify():
    driver = get_db_driver()
    with driver.session() as session:
        roles = session.run("MATCH (r:Role) RETURN r.name as name, r.permissions as perms").values()
        user = session.run("MATCH (u:User {email: 'pranavgupta1638@gmail.com'})-[:HAS_ROLE]->(r:Role) RETURN u.name, r.name").single()
        
        print("Roles in DB:")
        for r in roles:
            print(f"- {r[0]}: {r[1]}")
            
        if user:
            print(f"Verified Admin User: {user[0]} has role {user[1]}")
        else:
            print("Admin User NOT found or role NOT assigned!")

if __name__ == "__main__":
    verify()
