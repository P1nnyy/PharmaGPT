from typing import Dict, Any
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def upsert_user(driver, user_data: Dict[str, Any]):
    """
    Creates or updates a User node based on Google OAuth data.
    """
    query = """
    MERGE (u:User {email: $email})
    SET u.google_id = $google_id,
        u.name = $name,
        u.picture = $picture,
        u.updated_at = timestamp()
    RETURN u
    """
    with driver.session() as session:
        session.run(query, 
                    email=user_data.get("email"),
                    google_id=user_data.get("google_id"),
                    name=user_data.get("name"),
                    picture=user_data.get("picture"))

def _merge_supplier_tx(tx, name, details, user_email):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (s:Supplier {name: $name})
    
    // Create ownership if not exists
    MERGE (u)-[:OWNS]->(s)
    
    SET s.address = $address,
        s.gstin = $gstin,
        s.dl_no = $dl_no,
        s.phone = $phone,
        s.email = $email,
        s.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           name=name,
           address=details.get("Address"),
           gstin=details.get("GSTIN"),
           dl_no=details.get("DL_No"),
           phone=details.get("Phone_Number"),
           email=details.get("Email")
    )
