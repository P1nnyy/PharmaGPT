import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.database import get_db_driver
from src.domain.persistence.config import create_system_role, assign_user_role
from src.domain.persistence.access import upsert_user

def seed():
    print("Seed started...")
    driver = get_db_driver()
    
    # 1. Create Roles
    roles = {
        "Admin": ["all", "manage_users", "manage_config", "view_reports"],
        "Staff": ["view_reports", "edit_invoices", "manage_inventory"],
        "Employee": ["view_inventory", "create_drafts"]
    }
    
    for name, perms in roles.items():
        print(f"Creating role: {name}")
        create_system_role(name, perms)
        
    # 2. Upsert Initial Admin User
    admin_email = "pranavgupta1638@gmail.com"
    print(f"Upserting admin user: {admin_email}")
    user_data = {
        "email": admin_email,
        "google_id": "seed-admin-id",
        "name": "Pranav Gupta (Admin)",
        "picture": ""
    }
    upsert_user(driver, user_data)
    
    # 3. Assign Admin Role
    print(f"Assigning Admin role to {admin_email}")
    assign_user_role(admin_email, "Admin")
    
    print("Seeding completed successfully.")

if __name__ == "__main__":
    seed()
